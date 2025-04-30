import decimal

from reflex.vars.number import LiteralNumberVar


def test_decimal_number_operations():
    """Test that decimal.Decimal values work with NumberVar operations."""
    dec_num = LiteralNumberVar.create(decimal.Decimal("123.456"))  # type: ignore # noqa: PGH003
    assert isinstance(dec_num._var_value, decimal.Decimal)
    assert str(dec_num) == "123.456"

    result = dec_num + 10
    assert str(result) == "(123.456 + 10)"

    result = dec_num * 2
    assert str(result) == "(123.456 * 2)"

    result = dec_num / 2
    assert str(result) == "(123.456 / 2)"

    result = dec_num > 100
    assert str(result) == "(123.456 > 100)"

    result = dec_num < 200
    assert str(result) == "(123.456 < 200)"

    assert dec_num.json() == "123.456"


def test_decimal_var_type_compatibility():
    """Test that decimal.Decimal values are compatible with NumberVar type system."""
    dec_num = LiteralNumberVar.create(decimal.Decimal("123.456"))  # type: ignore # noqa: PGH003
    int_num = LiteralNumberVar.create(42)
    float_num = LiteralNumberVar.create(3.14)

    result = dec_num + int_num
    assert str(result) == "(123.456 + 42)"

    result = dec_num * float_num
    assert str(result) == "(123.456 * 3.14)"

    result = (dec_num + int_num) / float_num
    assert str(result) == "((123.456 + 42) / 3.14)"
