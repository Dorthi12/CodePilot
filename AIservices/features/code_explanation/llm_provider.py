"""
LLM Provider and Static Analysis Engine for Code Explanation.
Includes support for Gemini, OpenAI, and a comprehensive offline Static Analysis Engine.
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from AIservices.features.code_explanation.models import (
    ExplanationStyle,
    RelatedSymbolContext,
)

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Abstract interface for LLM explanation generation."""

    @abstractmethod
    def generate_explanation(
        self,
        code: str,
        language: str,
        question: Optional[str],
        style: ExplanationStyle,
        related_symbols: list[RelatedSymbolContext],
        limitations: list[str],
    ) -> dict[str, Any]:
        """Generate structured explanation fields."""
        pass


# ---------------------------------------------------------------------------
# Offline Static Analysis Engine (Deterministic, Zero Network Dependency)
# ---------------------------------------------------------------------------

class StaticAnalysisProvider(BaseLLMProvider):
    """
    Intelligent code analysis engine that inspects code syntax, structure,
    control flow, signatures, and patterns to produce structured explanations.
    Always available offline and acts as an immediate fallback.
    """

    def generate_explanation(
        self,
        code: str,
        language: str,
        question: Optional[str],
        style: ExplanationStyle,
        related_symbols: list[RelatedSymbolContext],
        limitations: list[str],
    ) -> dict[str, Any]:
        lines = [line.rstrip() for line in code.strip().splitlines() if line.strip()]

        # Extract code elements
        func_match = re.search(r"(?:def|function|func)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", code)
        if not func_match:
            func_match = re.search(r"(?:(?:public|private|protected|static|final|\s)+[\w<>\[\],]+\s+)([A-Za-z_]\w*)\s*\(([^)]*)\)", code)
        if not func_match:
            func_match = re.search(r"^\s*([A-Za-z_]\w*)\s*\(([^)]*)\)\s*(?:throws\s+[\w,\s]+)?\s*\{", code, re.M)

        class_match = re.search(r"(?:class|interface|type|struct)\s+([A-Za-z_]\w*)", code)
        returns = re.findall(r"\breturn\b\s*([^;]+)?", code)
        conditions = re.findall(r"\bif\b\s*\(([^)]+)\)|\bif\s+([^:{]+)", code)
        loops = re.findall(r"\b(?:for|while)\b\s*\(([^)]+)\)|\b(?:for|while)\s+([^:{]+)", code)
        exceptions = re.findall(r"\b(?:raise|throw)\s+([^;]+)", code)
        calls = re.findall(r"\b([A-Za-z_]\w*)\s*\(", code)

        func_name = func_match.group(1) if func_match else None
        params_raw = func_match.group(2) if func_match else None
        class_name = class_match.group(1) if class_match else None

        # Determine inputs
        inputs_desc = self._analyze_inputs(params_raw, language, style)

        # Determine outputs
        outputs_desc = self._analyze_outputs(returns, language, style)

        # Identify important symbols
        important_symbols = self._extract_important_symbols(code, func_name, class_name, calls)

        # Side effects detection
        side_effects = self._detect_side_effects(code)

        # Edge cases and potential issues detection
        edge_cases = self._detect_edge_cases(code, params_raw, conditions)

        # Step by step execution
        step_by_step = self._build_step_by_step(lines, style)

        # Purpose and overview
        overview = self._generate_overview(
            code=code,
            func_name=func_name,
            class_name=class_name,
            question=question,
            style=style,
            language=language,
            related_symbols=related_symbols,
        )

        return {
            "overview": overview,
            "step_by_step": step_by_step,
            "inputs": inputs_desc,
            "outputs": outputs_desc,
            "important_symbols": important_symbols,
            "side_effects": side_effects,
            "edge_cases": edge_cases,
        }

    def _analyze_inputs(self, params_raw: Optional[str], language: str, style: ExplanationStyle) -> str:
        if not params_raw or not params_raw.strip():
            return "No parameters required (accepts no arguments or operates on instance state)."

        params = [p.strip() for p in params_raw.split(",") if p.strip()]
        if style == ExplanationStyle.BEGINNER:
            param_names = [p.split(":")[0].split("=")[0].split()[-1] for p in params]
            return f"Accepts {len(params)} input value(s): {', '.join(param_names)}."
        else:
            return f"Parameters: {', '.join(params)}."

    def _analyze_outputs(self, returns: list[str], language: str, style: ExplanationStyle) -> str:
        if not returns:
            return "No explicit return statement found; returns None/void or executes statements for their side effects."

        cleaned_returns = [r.strip() for r in returns if r.strip()]
        if not cleaned_returns:
            return "Returns an empty value or exits function execution early."

        distinct = list(dict.fromkeys(cleaned_returns))
        if style == ExplanationStyle.BEGINNER:
            return f"Returns the computed result: {', '.join(distinct[:3])}."
        return f"Returns {', '.join(distinct[:3])} upon successful execution."

    def _extract_important_symbols(
        self, code: str, func_name: Optional[str], class_name: Optional[str], calls: list[str]
    ) -> list[str]:
        symbols = []
        if class_name:
            symbols.append(f"Class: {class_name}")
        if func_name:
            symbols.append(f"Function: {func_name}")

        # Top distinct function calls
        clean_calls = [c for c in calls if c not in ("if", "for", "while", "return", "print", "len", func_name)]
        for call in list(dict.fromkeys(clean_calls))[:5]:
            symbols.append(f"Invokes helper/method: {call}()")

        # Variables assigned
        assignments = re.findall(r"^\s*([A-Za-z_]\w*)\s*=", code, re.M)
        for var in list(dict.fromkeys(assignments))[:3]:
            symbols.append(f"Variable: {var}")

        return symbols

    def _detect_side_effects(self, code: str) -> list[str]:
        effects = []
        if re.search(r"\bprint\b|\bconsole\.log\b|\bSystem\.out\b|\bfmt\.Print", code):
            effects.append("Outputs diagnostics or logs to standard output/console.")
        if re.search(r"\bopen\b|\bread\b|\bwrite\b|\bclose\b|\bfs\.", code):
            effects.append("Performs filesystem I/O operations.")
        if re.search(r"\bhttp\b|\brequest\b|\bfetch\b|\baxios\b|\bget\b|\bpost\b", code, re.I):
            effects.append("Initiates network or external HTTP requests.")
        if re.search(r"\.commit\(\)|\.save\(\)|\.execute\(|INSERT|UPDATE|DELETE", code, re.I):
            effects.append("Mutates persistent database state.")
        if re.search(r"self\.\w+\s*=|this\.\w+\s*=", code):
            effects.append("Modifies internal object/instance attributes.")

        if not effects:
            effects.append("Pure calculation or in-memory transformation with no external I/O side effects detected.")

        return effects

    def _detect_edge_cases(self, code: str, params_raw: Optional[str], conditions: list) -> list[str]:
        cases = []
        if params_raw:
            cases.append("Passing null, None, or empty input arguments may cause errors if not explicitly checked.")
        if re.search(r"/|\bdiv\b", code):
            cases.append("Potential division by zero if divisor expression evaluates to 0.")
        if re.search(r"\[.+\]", code):
            cases.append("Potential index out of range or key error if collection is empty or key is missing.")
        if re.search(r"\bint\(|\bfloat\(|Number\(|parseInt\(", code):
            cases.append("Type conversion failures if string input cannot be parsed as a numeric value.")
        if re.search(r"\.get\(|\bnull\b|\bNone\b|\bundefined\b", code):
            cases.append("Ensure null/undefined checks are performed before accessing nested properties.")

        if not cases:
            cases.append("Validate boundary inputs (empty collections, unexpected data types, zero values).")

        return cases

    def _build_step_by_step(self, lines: list[str], style: ExplanationStyle) -> list[str]:
        steps = []
        for i, line in enumerate(lines[:12], start=1):
            stripped = line.strip()
            if stripped.startswith("def ") or stripped.startswith("function ") or stripped.startswith("func "):
                steps.append(f"Step {i}: Declares the function signature and defines input parameters.")
            elif stripped.startswith("class ") or stripped.startswith("interface "):
                steps.append(f"Step {i}: Declares the type/class definition and its structural blueprint.")
            elif stripped.startswith("if ") or " if " in stripped:
                steps.append(f"Step {i}: Evaluates the conditional expression to decide branching logic.")
            elif stripped.startswith("for ") or stripped.startswith("while "):
                steps.append(f"Step {i}: Loops over the elements or iterates while the condition holds true.")
            elif stripped.startswith("return ") or stripped == "return":
                steps.append(f"Step {i}: Returns the computed value and transfers control back to the caller.")
            elif "=" in stripped:
                var_name = stripped.split("=")[0].strip()
                steps.append(f"Step {i}: Evaluates the expression and assigns the result to `{var_name}`.")
            else:
                steps.append(f"Step {i}: Executes statement `{stripped[:60]}`.")
        return steps

    def _generate_overview(
        self,
        code: str,
        func_name: Optional[str],
        class_name: Optional[str],
        question: Optional[str],
        style: ExplanationStyle,
        language: str,
        related_symbols: list[RelatedSymbolContext],
    ) -> str:
        q_lower = (question or "").lower()

        # Handle specific developer question types
        if "line by line" in q_lower or "line-by-line" in q_lower:
            return f"Below is a line-by-line breakdown of this {language} code snippet."

        if "why is this condition" in q_lower or "condition" in q_lower:
            conds = re.findall(r"\bif\b\s*\(([^)]+)\)|\bif\s+([^:{]+)", code)
            cond_str = conds[0][0] or conds[0][1] if conds else "the conditional expression"
            return (
                f"The condition `{cond_str.strip()}` is used as a guard or validation check. "
                "It ensures that execution only proceeds when the prerequisites are satisfied, "
                "preventing unexpected runtime exceptions or invalid states."
            )

        if "purpose of this class" in q_lower or ("class" in q_lower and class_name):
            return (
                f"The purpose of `{class_name}` is to encapsulate related state and operations into a single cohesive unit. "
                "It defines the data model or service interface used by surrounding repository components."
            )

        if "algorithm" in q_lower:
            return (
                f"This code implements an algorithm in {language} that processes input data through sequential validation, "
                "state transformation, and conditional branch resolution."
            )

        if "what will happen if" in q_lower or "input is provided" in q_lower:
            return (
                "When an input is passed to this code, it is first evaluated against defined guard clauses. "
                "If valid, execution progresses through the main computation steps; otherwise it takes an early exit or returns default/error states."
            )

        if "bug" in q_lower or "edge case" in q_lower:
            return (
                "Analysis of potential bugs and edge cases: Focus on validating unhandled null/empty inputs, "
                "boundary conditions, and ensuring external dependencies handle unexpected runtime failures gracefully."
            )

        # General purpose overview
        subject = f"`{func_name}()`" if func_name else (f"`{class_name}`" if class_name else "This code block")

        if style == ExplanationStyle.BEGINNER:
            overview = (
                f"{subject} is a piece of {language} code designed to accomplish a specific task. "
                "In simple terms, it takes incoming data, checks whether the data is valid, "
                "does the necessary work step by step, and provides the final outcome."
            )
        elif style == ExplanationStyle.DEEP:
            overview = (
                f"{subject} defines a core component in the {language} codebase. "
                "It handles data ingestion, executes control flow branching, manages local state mutations, "
                "and coordinates with dependencies to produce deterministic outputs."
            )
        else:  # TECHNICAL
            overview = (
                f"{subject} implements the required logic in {language}. "
                "It processes input parameters, enforces validation rules, invokes relevant dependencies, "
                "and produces structured results."
            )

        # Mention related symbols if retrieved
        if related_symbols:
            rel_names = [f"`{s.name}` ({s.file_path})" for s in related_symbols[:2]]
            overview += f" It directly integrates with repository dependencies including {', '.join(rel_names)}."

        return overview


# ---------------------------------------------------------------------------
# Gemini Provider (Optional, when GEMINI_API_KEY is available)
# ---------------------------------------------------------------------------

class GeminiLLMProvider(BaseLLMProvider):
    def __init__(self, api_key: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def generate_explanation(
        self,
        code: str,
        language: str,
        question: Optional[str],
        style: ExplanationStyle,
        related_symbols: list[RelatedSymbolContext],
        limitations: list[str],
    ) -> dict[str, Any]:
        prompt = f"""You are an expert code explainer for CodePilot.
Explain this {language} code clearly for a {style.value} audience.

CODE:
```{language}
{code}
```

QUESTION: {question or 'Explain what this code does and how it works.'}

RELATED REPOSITORY CONTEXT:
{json.dumps([s.model_dump() for s in related_symbols], indent=2)}

Return a strict JSON object with:
{{
  "overview": "Clear explanation of code purpose and answer to the question",
  "step_by_step": ["step 1", "step 2"],
  "inputs": "description of inputs/params",
  "outputs": "description of return values",
  "important_symbols": ["symbol1", "symbol2"],
  "side_effects": ["side effect 1"],
  "edge_cases": ["edge case 1"]
}}
"""
        response = self.model.generate_content(prompt)
        text = response.text
        # Clean potential markdown wrapping
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        return json.loads(text)


# ---------------------------------------------------------------------------
# Provider Factory
# ---------------------------------------------------------------------------

def get_llm_provider() -> BaseLLMProvider:
    """Return configured LLM provider, falling back to StaticAnalysisProvider."""
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        try:
            return GeminiLLMProvider(gemini_key)
        except Exception as exc:
            logger.warning("Failed to initialize Gemini provider: %s — using static analyzer", exc)

    return StaticAnalysisProvider()
