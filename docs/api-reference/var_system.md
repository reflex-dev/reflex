# Reflex's Var System

## Motivation

Reflex supports some basic operations in state variables on the frontend.
Reflex automatically converts variable operations from Python into a JavaScript equivalent.

Here's an example of a Reflex conditional in Python that returns "Pass" if the threshold is equal to or greater than 50 and "Fail" otherwise:

```py
rx.cond(
    State.threshold >= 50,
    "Pass",
    "Fail",
)
```

 The conditional to roughly the following in Javascript:

```js
state.threshold >= 50 ? "Pass" : "Fail";
```

## Overview

Simply put, a `Var` in Reflex represents a Javascript expression.
If the type is known, it can be any of the following:

- `NumberVar` represents an expression that evaluates to a Javascript `number`. `NumberVar` can support both integers and floating point values
- `BooleanVar` represents a boolean expression. For example: `false`, `3 > 2`.
- `StringVar` represents an expression that evaluates to a string. For example: `'hello'`, `(2).toString()`.
- `ArrayVar` represents an expression that evaluates to an array object. For example: `[1, 2, 3]`, `'words'.split()`.
- `ObjectVar` represents an expression that evaluates to an object. For example: `\{a: 2, b: 3}`, `\{deeply: \{nested: \{value: false}}}`.
- `NoneVar` represent null values. These can be either `undefined` or `null`.

## Creating Vars

State fields are converted to `Var` by default. Additionally, you can create a `Var` from Python values using `rx.Var.create()`:

```py
rx.Var.create(4) # NumberVar
rx.Var.create("hello") # StringVar
rx.Var.create([1, 2, 3]) # ArrayVar
```

If you want to explicitly create a `Var` from a raw Javascript string, you can instantiate `rx.Var` directly:

```py
rx.Var("2", _var_type=int).guess_type() # NumberVar
```

In the example above, `.guess_type()` will attempt to downcast from a generic `Var` type into `NumberVar`.
For this example, calling the function `.to(int)` can also be used in place of `.guess_type()`.

## Operations

The `Var` system also supports some other basic operations.
For example, `NumberVar` supports basic arithmetic operations like `+` and `-`, as in Python.
It also supports comparisons that return a `BooleanVar`.

Custom `Var` operations can also be defined:

```py
from reflex.vars import var_operation, var_operation_return, ArrayVar, NumberVar

@var_operation
def multiply_array_values(a: ArrayVar):
    return var_operation_return(
        js_expression=f"\{a}.reduce((p, c) => p * c, 1)",
        var_type=int,
    )

def factorial(value: NumberVar):
    return rx.cond(
        value <= 1,
        1,
        multiply_array_values(rx.Var.range(1, value+1))
    )
```

Use `js_expression` to pass explicit JavaScript expressions; in the `multiply_array_values` example, we pass in a JavaScript expression that calculates the product of all elements in an array called `a` by using the reduce method to multiply each element with the accumulated result, starting from an initial value of 1.
Later, we leverage `rx.cond` in the' factorial' function, we instantiate an array using the `range` function, and pass this array to `multiply_array_values`.
