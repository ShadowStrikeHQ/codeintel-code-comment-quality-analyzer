import argparse
import ast
import logging
import os
import re
import sys
from typing import List, Tuple, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CommentQualityAnalyzer:
    """
    Analyzes the quality and completeness of code comments in Python files.
    """

    def __init__(self, filename: str, style_guide: Dict[str, Any] = None) -> None:
        """
        Initializes the CommentQualityAnalyzer with the filename and optional style guide.

        Args:
            filename (str): The path to the Python file to analyze.
            style_guide (Dict[str, Any], optional): A dictionary containing style guide rules. Defaults to None.
        """
        self.filename = filename
        self.style_guide = style_guide if style_guide else {}
        self.source_code = ""
        self.tree = None

        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                self.source_code = f.read()
            self.tree = ast.parse(self.source_code)
        except FileNotFoundError:
            logging.error(f"File not found: {self.filename}")
            raise
        except Exception as e:
            logging.error(f"Error reading or parsing file: {self.filename} - {e}")
            raise
    
    def _extract_docstring(self, node: ast.AST) -> str:
        """
        Extracts the docstring from an AST node.

        Args:
            node (ast.AST): The AST node to extract the docstring from.

        Returns:
            str: The docstring, or an empty string if no docstring is found.
        """
        if hasattr(node, 'body') and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            return node.body[0].value.value
        return ""
    

    def check_missing_comments(self) -> List[Tuple[int, str, str]]:
        """
        Checks for missing comments on functions, classes, and complex logic blocks.

        Returns:
            List[Tuple[int, str, str]]: A list of tuples, where each tuple contains:
                - The line number where the missing comment was detected.
                - The type of element missing the comment (e.g., "function", "class", "complex logic").
                - A descriptive message about the missing comment.
        """
        missing_comments: List[Tuple[int, str, str]] = []

        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = self._extract_docstring(node)
                if not docstring:
                    missing_comments.append((node.lineno, "function", f"Missing docstring for function: {node.name}"))

            elif isinstance(node, ast.ClassDef):
                docstring = self._extract_docstring(node)
                if not docstring:
                    missing_comments.append((node.lineno, "class", f"Missing docstring for class: {node.name}"))

            elif isinstance(node, ast.If):
                # Heuristic for complex logic: Check for nested ifs or long conditions
                if len(node.body) > 3 or any(isinstance(n, ast.If) for n in node.body) or len(ast.dump(node.test)) > 100:  # type: ignore
                    # Check for a preceding comment
                    if node.lineno > 1:
                        with open(self.filename, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            if node.lineno - 2 >= 0:  # type: ignore
                                prev_line = lines[node.lineno - 2].strip() # type: ignore
                                if not prev_line.startswith("#"):
                                    missing_comments.append((node.lineno, "complex logic", "Missing comment for complex if statement"))
                    else:
                         missing_comments.append((node.lineno, "complex logic", "Missing comment for complex if statement"))

        return missing_comments

    def enforce_comment_style_consistency(self) -> List[Tuple[int, str, str]]:
        """
        Enforces comment style consistency based on the provided style guide.

        Returns:
            List[Tuple[int, str, str]]: A list of tuples, where each tuple contains:
                - The line number where the style violation was detected.
                - The type of style violation (e.g., "indentation", "prefix").
                - A descriptive message about the style violation.
        """
        style_violations: List[Tuple[int, str, str]] = []
        
        if not self.style_guide:
            logging.warning("No style guide provided. Skipping style consistency checks.")
            return style_violations

        with open(self.filename, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                line = line.rstrip()
                if line.strip().startswith("#"):  # Check for comments
                    comment_text = line.split("#", 1)[1].strip()

                    # Check for minimum comment length
                    if "min_length" in self.style_guide and len(comment_text) < self.style_guide["min_length"]:
                        style_violations.append((i, "length", f"Comment is too short (min length: {self.style_guide['min_length']})"))

                    # Check for required comment prefix
                    if "required_prefix" in self.style_guide and not comment_text.startswith(self.style_guide["required_prefix"]):
                        style_violations.append((i, "prefix", f"Comment does not start with required prefix: {self.style_guide['required_prefix']}"))

        return style_violations

    def identify_outdated_comments(self) -> List[Tuple[int, str, str]]:
        """
        Identifies outdated or misleading comments based on code changes.  This is a simplified version
        that searches for comments near changed lines (simulated with regex).  A real implementation
        would integrate with a version control system.

        Returns:
            List[Tuple[int, str, str]]: A list of tuples, where each tuple contains:
                - The line number where the outdated comment was detected.
                - The type of issue (e.g., "outdated", "misleading").
                - A descriptive message about the outdated comment.
        """
        outdated_comments: List[Tuple[int, str, str]] = []

        # Simulate code changes with a regex pattern.  This is a simplified example.
        changed_lines_pattern = r"result = val \+ 5" #Example pattern to look for

        with open(self.filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            if re.search(changed_lines_pattern, line):
                # Check lines above and below for comments that might be outdated
                for offset in range(-3, 4):  # Check a window of +/- 3 lines
                    check_line_num = i + offset
                    if 0 <= check_line_num < len(lines):
                        check_line = lines[check_line_num].strip()
                        if check_line.startswith("#"):
                            # Simple heuristic: look for comments mentioning variables in the changed line
                            for var in re.findall(r'\b\w+\b', line):  # Find all words in changed line
                                if var in check_line and len(var) > 2:
                                    outdated_comments.append((check_line_num + 1, "outdated", f"Possible outdated comment near changed line. Comment might be related to variable: {var}"))
                                    break  # Only flag the comment once

        return outdated_comments

def setup_argparse() -> argparse.ArgumentParser:
    """
    Sets up the argument parser for the command line interface.

    Returns:
        argparse.ArgumentParser: The configured argument parser.
    """
    parser = argparse.ArgumentParser(description="Evaluate the quality and completeness of code comments.")
    parser.add_argument("filename", help="The Python file to analyze.")
    parser.add_argument("--style-guide", help="Path to a JSON file containing comment style guide rules.", default=None)
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    return parser


def main() -> None:
    """
    The main function of the code comment quality analyzer.
    """
    parser = setup_argparse()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        style_guide = {}
        if args.style_guide:
            try:
                import json
                with open(args.style_guide, 'r', encoding='utf-8') as f:
                    style_guide = json.load(f)
            except FileNotFoundError:
                logging.error(f"Style guide file not found: {args.style_guide}")
                sys.exit(1)
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in style guide file: {args.style_guide} - {e}")
                sys.exit(1)

        analyzer = CommentQualityAnalyzer(args.filename, style_guide)

        missing_comments = analyzer.check_missing_comments()
        style_violations = analyzer.enforce_comment_style_consistency()
        outdated_comments = analyzer.identify_outdated_comments()

        if missing_comments:
            print("\nMissing Comments:")
            for line, comment_type, message in missing_comments:
                print(f"  Line {line}: {comment_type} - {message}")

        if style_violations:
            print("\nStyle Violations:")
            for line, violation_type, message in style_violations:
                print(f"  Line {line}: {violation_type} - {message}")

        if outdated_comments:
            print("\nPossible Outdated Comments:")
            for line, issue_type, message in outdated_comments:
                print(f"  Line {line}: {issue_type} - {message}")

        if not missing_comments and not style_violations and not outdated_comments:
            print("No issues found with code comments.")

    except FileNotFoundError:
        sys.exit(1)
    except Exception as e:
        logging.exception("An unexpected error occurred:")
        sys.exit(1)

if __name__ == "__main__":
    main()

# Example Usage:
# 1. Run the analyzer on a file: python main.py my_code.py
# 2. Run with a style guide: python main.py my_code.py --style-guide style_guide.json
# 3. Run with verbose logging: python main.py my_code.py --verbose
# Example style_guide.json:
# {
#   "min_length": 10,
#   "required_prefix": "TODO:"
# }