from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from numbers import Real
from typing import Any, cast

import sympy as sp

Sampler = Callable[[dict[str, Any]], Any]
Validator = Callable[[Any, dict[str, Any]], None]


class ParameterError(ValueError):
    """Raised when a parameter definition or equation set is invalid."""


class InsufficientInformation(Exception):
    """Raised when required values cannot be derived or sampled yet."""


@dataclass(frozen=True)
class Variable:
    sample: Sampler | None = None
    validate: Validator | None = None
    order: int | None = None
    description: str | None = None


@dataclass(frozen=True)
class _Equation:
    source: str
    relation: sp.Equality
    symbols: frozenset[str]
    description: str | None = None


@dataclass
class ParameterDAG:
    """Resolve declared variables by equation deduction and fallback sampling."""

    variables: Mapping[str, Variable] | None = None
    equations: Iterable[str] = ()
    rel_tol: float = 1e-9
    abs_tol: float = 1e-12
    _variables: dict[str, Variable] = field(default_factory=dict, init=False)
    _symbols: dict[str, sp.Symbol] = field(default_factory=dict, init=False)
    _equations: list[_Equation] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        initial_variables = dict(self.variables or {})
        initial_equations = tuple(self.equations)
        self.variables = None
        self.equations = ()
        for name, variable in initial_variables.items():
            if not isinstance(variable, Variable):
                raise TypeError(f"Variable definition for {name!r} must be a Variable.")
            self.add_variable(
                name,
                sample=variable.sample,
                validate=variable.validate,
                order=variable.order,
                description=variable.description,
            )
        for equation in initial_equations:
            self.add_equation(equation)

    @property
    def variable_names(self) -> frozenset[str]:
        return frozenset(self._variables)

    @property
    def parameter_names(self) -> frozenset[str]:
        return self.variable_names

    def add_variable(
        self,
        name: str,
        *,
        sample: Sampler | None = None,
        validate: Validator | None = None,
        order: int | None = None,
        description: str | None = None,
        override: bool = False,
    ) -> ParameterDAG:
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_]\w*", name):
            raise ValueError(f"Invalid variable name {name!r}.")
        if name in self._variables and not override:
            raise ValueError(f"Variable {name!r} is already declared.")
        if sample is not None and not callable(sample):
            raise TypeError("sample must be callable or None.")
        if validate is not None and not callable(validate):
            raise TypeError("validate must be callable or None.")
        if order is not None and (
            isinstance(order, bool) or not isinstance(order, int)
        ):
            raise TypeError("order must be an integer or None.")
        if order is not None and any(
            other_name != name and variable.order == order
            for other_name, variable in self._variables.items()
        ):
            raise ValueError(f"Variable order {order} is already in use.")

        self._variables[name] = Variable(sample, validate, order, description)
        self._symbols[name] = sp.Symbol(name)
        return self

    def add(
        self,
        name: str,
        *,
        sampler: Sampler | None = None,
        sample: Sampler | None = None,
        validate: Validator | None = None,
        order: int | None = None,
        description: str | None = None,
        override: bool = False,
    ) -> ParameterDAG:
        if sampler is not None and sample is not None:
            raise TypeError("Provide either sample or sampler, not both.")
        return self.add_variable(
            name,
            sample=sample if sample is not None else sampler,
            validate=validate,
            order=order,
            description=description,
            override=override,
        )

    def remove_variable(self, name: str) -> ParameterDAG:
        if name not in self._variables:
            raise ValueError(f"Unknown variable {name!r}.")
        dependent = [
            equation.source for equation in self._equations if name in equation.symbols
        ]
        if dependent:
            raise ValueError(
                f"Cannot remove variable {name!r}; equations still reference it: {dependent}."
            )
        del self._variables[name]
        del self._symbols[name]
        return self

    def add_equation(self, equation: str) -> ParameterDAG:
        if not isinstance(equation, str):
            raise TypeError("An equation must be provided as a string.")
        match = re.fullmatch(r"\s*(.*?)\s*(?<![<>=!])=(?!=)\s*(.*?)\s*", equation)
        if match is None or not match.group(1) or not match.group(2):
            raise ValueError(f"Invalid equation {equation!r}; expected 'x = y + 1'.")
        try:
            left = sp.sympify(match.group(1), locals=dict(self._symbols))
            right = sp.sympify(match.group(2), locals=dict(self._symbols))
        except (sp.SympifyError, SyntaxError, TypeError, ValueError) as exc:
            raise ValueError(f"Could not parse equation {equation!r}: {exc}") from exc

        relation = cast(sp.Equality, sp.Equality(left, right, evaluate=False))
        unknown = (left.free_symbols | right.free_symbols) - set(self._symbols.values())
        if unknown:
            names = ", ".join(sorted(str(symbol) for symbol in unknown))
            raise ValueError(
                f"Equation {equation!r} references undeclared variable(s): {names}."
            )
        symbols = frozenset(
            name
            for name, symbol in self._symbols.items()
            if symbol in relation.free_symbols
        )
        if not symbols:
            raise ValueError(f"Equation {equation!r} contains no declared variables.")
        expression = sp.simplify(left - right)
        if expression == 0:
            raise ValueError(f"Equation {equation!r} imposes no constraint.")

        candidate = _Equation(equation, relation, symbols)
        self._validate_equation_unambiguous(candidate)
        self._validate_equation_consistency((*self._equations, candidate))
        self._equations.append(candidate)
        return self

    def equation(
        self, equation: str, *, description: str | None = None
    ) -> ParameterDAG:
        if description is None:
            return self.add_equation(equation)
        match = re.fullmatch(r"\s*(.*?)\s*(?<![<>=!])=(?!=)\s*(.*?)\s*", equation)
        if match is None:
            raise ValueError(f"Invalid equation {equation!r}.")
        self.add_equation(equation)
        added = self._equations[-1]
        self._equations[-1] = _Equation(
            added.source, added.relation, added.symbols, description
        )
        return self

    def remove_equation(self, equation: str) -> ParameterDAG:
        for index, existing in enumerate(self._equations):
            if existing.source == equation:
                candidate = self._equations[:index] + self._equations[index + 1 :]
                self._validate_equation_consistency(candidate)
                del self._equations[index]
                return self
        raise ValueError(f"Unknown equation {equation!r}.")

    def resolve(
        self, supplied: Mapping[str, Any], *, context: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        if not isinstance(supplied, Mapping):
            raise TypeError("supplied must be a mapping of variable names to values.")
        unknown = set(supplied) - self._variables.keys()
        if unknown:
            raise ParameterError(f"Unknown variable(s): {', '.join(sorted(unknown))}.")
        if any(value is None for value in supplied.values()):
            raise ParameterError(
                "None is not a supplied value; omit the variable instead."
            )
        values = dict(context or {})
        collisions = values.keys() & self._variables.keys()
        if collisions:
            raise ParameterError(
                f"Context shadows declared variable(s): {', '.join(sorted(collisions))}."
            )
        values.update(supplied)

        while missing := self._variables.keys() - values.keys():
            derived = self._derive_one(values, missing)
            if derived is not None:
                name, value = derived
                values[name] = value
                continue

            sampled = self._sample_one(values, missing)
            if sampled is None:
                names = ", ".join(sorted(missing))
                raise InsufficientInformation(
                    f"Could not resolve variable(s): {names}; no equation could derive them "
                    "and every applicable sampler lacked sufficient information."
                )
            name, value = sampled
            values[name] = value

        return {name: values[name] for name in self._variables}

    def check(self, values: Mapping[str, Any]) -> None:
        if not isinstance(values, Mapping):
            raise TypeError("values must be a mapping of variable names to values.")
        missing = self._variables.keys() - values.keys()
        unknown = values.keys() - self._variables.keys()
        if missing or unknown:
            raise ParameterError(
                f"Values must contain exactly the declared variables; missing={sorted(missing)}, "
                f"unknown={sorted(unknown)}."
            )
        if any(value is None for value in values.values()):
            raise ParameterError("None is not a valid resolved value.")
        self._check_equations(values)
        self._validate(values)

    def _derive_one(
        self, values: Mapping[str, Any], missing: Iterable[str]
    ) -> tuple[str, Any] | None:
        missing_names = set(missing)
        for equation in self._equations:
            for name in equation.symbols & missing_names:
                symbol = self._symbols[name]
                try:
                    solutions = sp.solve(equation.relation, symbol, dict=False)
                except (NotImplementedError, ValueError, TypeError):
                    continue
                if not isinstance(solutions, (list, tuple)):
                    solutions = [solutions]
                usable = []
                for solution in solutions:
                    solution = sp.sympify(solution)
                    if symbol in solution.free_symbols:
                        continue
                    free_names = {str(free) for free in solution.free_symbols}
                    if not free_names <= values.keys():
                        continue
                    try:
                        usable.append(self._evaluate(solution, values, target=name))
                    except ParameterError:
                        continue
                if len(usable) == 1:
                    return name, usable[0]
                if len(usable) > 1 and any(
                    not self._equal(usable[0], value) for value in usable[1:]
                ):
                    raise ParameterError(
                        f"Equation {equation.source!r} gives ambiguous values for {name!r}: {usable}."
                    )
                if usable:
                    return name, usable[0]
        return None

    def _sample_one(
        self, values: Mapping[str, Any], missing: Iterable[str]
    ) -> tuple[str, Any] | None:
        names = list(missing)
        names.sort(
            key=lambda name: (
                self._variables[name].order is None,
                self._variables[name].order
                if self._variables[name].order is not None
                else 0,
            )
        )
        for name in names:
            variable = self._variables[name]
            if variable.sample is None:
                continue
            try:
                result = variable.sample(dict(values))
            except InsufficientInformation:
                continue
            if result is None:
                raise ParameterError(f"Sampler for {name!r} returned None.")
            return name, result
        return None

    def _check_equations(self, values: Mapping[str, Any]) -> None:
        for equation in self._equations:
            left = self._evaluate(equation.relation.lhs, values, target=equation.source)
            right = self._evaluate(
                equation.relation.rhs, values, target=equation.source
            )
            if not self._equal(left, right):
                raise ParameterError(
                    f"Equation {equation.source!r} is not satisfied: {left!r} != {right!r}."
                )

    def _validate(self, values: Mapping[str, Any]) -> None:
        for name, variable in self._variables.items():
            if variable.validate is None:
                continue
            try:
                variable.validate(values[name], dict(values))
            except InsufficientInformation:
                raise
            except Exception as exc:
                description = (
                    f" ({variable.description})" if variable.description else ""
                )
                raise ParameterError(
                    f"Invalid variable {name!r}{description}: {exc}"
                ) from exc

    def _evaluate(
        self, expression: sp.Basic, values: Mapping[str, Any], *, target: str
    ) -> Any:
        substitutions = {}
        for symbol in expression.free_symbols:
            name = str(symbol)
            if name not in values:
                raise ParameterError(
                    f"Missing value for {name!r} while evaluating {target!r}."
                )
            try:
                substitutions[symbol] = sp.sympify(values[name])
            except (sp.SympifyError, TypeError, ValueError) as exc:
                raise ParameterError(
                    f"Value for {name!r} is not numeric: {values[name]!r}."
                ) from exc
        result = expression.subs(substitutions)
        if result.free_symbols or result.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
            raise ParameterError(f"Could not evaluate {target!r}: {result}.")
        if isinstance(result, sp.Integer):
            return int(result)
        if isinstance(result, sp.Rational):
            return int(result) if result.q == 1 else float(result)
        if result.is_number:
            numeric = complex(sp.N(result))
            if math.isclose(numeric.imag, 0.0, rel_tol=0.0, abs_tol=self.abs_tol):
                number = numeric.real
                nearest = round(number)
                return (
                    int(nearest)
                    if math.isclose(number, nearest, rel_tol=0.0, abs_tol=self.abs_tol)
                    else number
                )
            return numeric
        return result

    def _equal(self, left: Any, right: Any) -> bool:
        if (
            isinstance(left, Real)
            and not isinstance(left, bool)
            and isinstance(right, Real)
            and not isinstance(right, bool)
        ):
            return math.isclose(
                float(left), float(right), rel_tol=self.rel_tol, abs_tol=self.abs_tol
            )
        return left == right

    @staticmethod
    def _validate_equation_unambiguous(equation: _Equation) -> None:
        for name in equation.symbols:
            symbol = sp.Symbol(name)
            try:
                solutions = sp.solve(equation.relation, symbol, dict=False)
            except (NotImplementedError, ValueError, TypeError) as exc:
                raise ValueError(
                    f"Could not establish a unique solution for {name!r} in {equation.source!r}."
                ) from exc
            if not isinstance(solutions, (list, tuple)):
                solutions = [solutions]
            unique = []
            for solution in solutions:
                solution = sp.simplify(sp.sympify(solution))
                if symbol not in solution.free_symbols and solution not in unique:
                    unique.append(solution)
            if len(unique) != 1:
                raise ValueError(
                    f"Equation {equation.source!r} does not uniquely determine variable {name!r}."
                )

    @staticmethod
    def _validate_equation_consistency(equations: Iterable[_Equation]) -> None:
        equations = tuple(equations)
        if not equations:
            return
        symbols = sorted(
            {sp.Symbol(name) for equation in equations for name in equation.symbols},
            key=str,
        )
        try:
            solutions = sp.solve(
                [equation.relation for equation in equations], symbols, dict=True
            )
        except (NotImplementedError, ValueError, TypeError, RecursionError):
            return
        if solutions == []:
            raise ValueError("The equation set is contradictory.")
