"""安全计算器的单元测试（F2 第一批清单）。

历史背景：这个工具的前身是 eval() RCE（P0 ①），现在的两层白名单
（字符正则 + AST 节点）是安全边界本身，必须有测试钉住。
"""

import pytest

from agents.tools.calculator import calculate, safe_calculate

# ---------- 正常算术 ----------


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1+2*3", 7),
        ("(1+2)*3", 9),
        ("10/4", 2.5),
        ("10//4", 2),
        ("10%3", 1),
        ("2**10", 1024),
        ("-5+3", -2),
        ("+7", 7),
        ("3.5*2", 7.0),
        (" 1 + 1 ", 2),
    ],
)
def test_valid_expressions(expression, expected):
    assert safe_calculate(expression) == expected


# ---------- 注入与非法输入拒绝 ----------


@pytest.mark.parametrize(
    "malicious",
    [
        "__import__('os').system('id')",
        "().__class__.__bases__",
        "open('/etc/passwd')",
        "1;import os",
        "a+1",
        "1 if 1 else 2",
        '"1"+"2"',
    ],
)
def test_injection_rejected(malicious):
    with pytest.raises((ValueError, SyntaxError)):
        safe_calculate(malicious)


def test_empty_expression_rejected():
    with pytest.raises(ValueError):
        safe_calculate("")
    with pytest.raises(ValueError):
        safe_calculate("   ")


def test_too_long_expression_rejected():
    with pytest.raises(ValueError, match="过长"):
        safe_calculate("1+" * 60 + "1")


def test_boolean_constant_rejected():
    # True/False 是 ast.Constant 但不是数字，字符白名单先拦；直捣 AST 层验证第二道防线
    with pytest.raises(ValueError):
        safe_calculate("True+1")


# ---------- 资源耗尽防护 ----------


def test_power_bomb_rejected():
    # 9**9**9 右结合 = 9**(9**9)，中间值 387420489 超过指数上限
    with pytest.raises(ValueError, match="幂运算"):
        safe_calculate("9**9**9")


def test_power_within_limit_allowed():
    assert safe_calculate("2**128") == 2**128


def test_power_base_limit():
    with pytest.raises(ValueError, match="幂运算"):
        safe_calculate("1000001**2")


# ---------- tool 包装层（LLM 实际调用的入口） ----------


def test_tool_returns_integer_string():
    # 整数值的 float 应显示为 int（"4" 而不是 "4.0"），LLM 转述时更自然
    assert calculate.invoke({"expression": "8/2"}) == "4"


def test_tool_division_by_zero_friendly():
    assert calculate.invoke({"expression": "1/0"}) == "计算失败：除数不能为零"


def test_tool_never_raises_on_bad_input():
    # 工具层对任何垃圾输入都返回可读文案（异常会中断整轮对话）
    result = calculate.invoke({"expression": "__import__('os')"})
    assert result.startswith("计算失败")
