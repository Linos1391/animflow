"""The utils."""
import ast
import operator

class Constant:
    """Manage those constants effectively."""
    JSON_FILE: str = "animflow.json"
    GIF_FILE: str = "{index}.webp"
    COMPATIBLE_ERROR: str = "Animation {name} isn't compatible."

class EvalUtils:
    """Mostly for eval."""
    @staticmethod
    def safe_json_eval(value):
        """Parse DBus reply values safely.

        The Wayland extension returns Python literal structures such as
        list[dict] or dict. Only parse string values as Python literals;
        if the value is not a literal, keep the original string unchanged.
        """
        if isinstance(value, str):
            try:
                return ast.literal_eval(value.replace('true', 'True')
                                             .replace('false', 'False')
                                             .replace('null', 'None'))
            except (ValueError, SyntaxError):
                return value
        return value

    @staticmethod
    def safe_math_eval(expr, **kwargs) -> int:
        """I do not trust you guys. I will not trust you guys.
        Add to `**kwargs` yourself and rethink the consequences.
        """
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            **kwargs
        }

        def eval_node(node) -> int | float:
            if isinstance(node, ast.BinOp):  # Binary operations
                left = eval_node(node.left)
                right = eval_node(node.right)
                op_func = operators.get(type(node.op))
                if op_func:
                    return op_func(left, right)
                else:
                    raise TypeError(f"Unsupported operator: {type(node.op)}")
            elif isinstance(node, ast.UnaryOp):  # Unary operations
                operand = eval_node(node.operand)
                op_func = operators.get(type(node.op))
                if op_func:
                    return op_func(operand)
                else:
                    raise TypeError(f"Unsupported unary operator: {type(node.op)}")
            elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):  # Numbers
                return node.value
            else:
                raise TypeError(f"Unsupported node type: {type(node).__name__}")

        tree = ast.parse(expr, mode='eval')
        return int(eval_node(tree.body))

    @staticmethod
    def location_format(x: str, y: str, attributes: dict):
        """Just a dynamic location format"""
        return (EvalUtils.safe_math_eval(x.format_map(attributes)),
                EvalUtils.safe_math_eval(y.format_map(attributes)))
