"""A module for generating Bezier easing functions."""

# These values are established by empiricism with tests (tradeoff: performance VS precision)
NEWTON_ITERATIONS = 4
NEWTON_MIN_SLOPE = 0.001
SUBDIVISION_PRECISION = 0.0000001
SUBDIVISION_MAX_ITERATIONS = 10
kSplineTableSize = 11
kSampleStepSize = 1.0 / (kSplineTableSize - 1.0)


def A(aA1, aA2):
    """Calculate A.

    Args:
        aA1: The first value.
        aA2: The second value.

    Returns:
        The calculated value.
    """
    return 1.0 - 3.0 * aA2 + 3.0 * aA1


def B(aA1, aA2):
    """Calculate B.

    Args:
        aA1: The first value.
        aA2: The second value.

    Returns:
        The calculated value.
    """
    return 3.0 * aA2 - 6.0 * aA1


def C(aA1):
    """Calculate C.

    Args:
        aA1: The first value.

    Returns:
        The calculated value.
    """
    return 3.0 * aA1


def calcBezier(aT, aA1, aA2):
    """Calculate Bezier.

    Args:
        aT: The time.
        aA1: The first value.
        aA2: The second value.

    Returns:
        x(t) given t, x1, and x2, or y(t) given t, y1, and y2.
    """
    return ((A(aA1, aA2) * aT + B(aA1, aA2)) * aT + C(aA1)) * aT


def getSlope(aT, aA1, aA2):
    """Calculate slope.

    Args:
        aT: The time.
        aA1: The first value.
        aA2: The second value.

    Returns:
        dx/dt given t, x1, and x2, or dy/dt given t, y1, and y2.
    """
    return 3.0 * A(aA1, aA2) * aT * aT + 2.0 * B(aA1, aA2) * aT + C(aA1)


def binarySubdivide(aX, aA, aB, mX1, mX2):
    """Perform a binary subdivide.

    Args:
        aX: The x value.
        aA: The a value.
        aB: The b value.
        mX1: The x1 value.
        mX2: The x2 value.

    Returns:
        The t value.
    """
    current_x = aA
    current_t = 0
    i = 0
    while True:
        i += 1
        if i >= SUBDIVISION_MAX_ITERATIONS:
            break
        current_t = aA + (aB - aA) / 2.0
        current_x = calcBezier(current_t, mX1, mX2) - aX
        if current_x > 0.0:
            aB = current_t
        else:
            aA = current_t
        if abs(current_x) <= SUBDIVISION_PRECISION:
            break
    return current_t


def newtonRaphsonIterate(aX, aGuessT, mX1, mX2):
    """Perform a Newton-Raphson iteration.

    Args:
        aX: The x value.
        aGuessT: The guess value.
        mX1: The x1 value.
        mX2: The x2 value.

    Returns:
        The t value.
    """
    for _ in range(NEWTON_ITERATIONS):
        current_slope = getSlope(aGuessT, mX1, mX2)
        if current_slope == 0.0:
            return aGuessT
        current_x = calcBezier(aGuessT, mX1, mX2) - aX
        aGuessT -= current_x / current_slope
    return aGuessT


def LinearEasing(x):
    """Linear easing function.

    Args:
        x: The x value.

    Returns:
        The x value.
    """
    return x


def bezier(mX1, mY1, mX2, mY2):
    """Generate a Bezier easing function.

    Args:
        mX1: The x1 value.
        mY1: The y1 value.
        mX2: The x2 value.
        mY2: The y2 value.

    Raises:
        ValueError: If the x values are not in the [0, 1] range.

    Returns:
        The Bezier easing function.
    """
    if not (0 <= mX1 <= 1 and 0 <= mX2 <= 1):
        raise ValueError("bezier x values must be in [0, 1] range")

    if mX1 == mY1 and mX2 == mY2:
        return LinearEasing

    # Precompute samples table
    sampleValues = [
        calcBezier(i * kSampleStepSize, mX1, mX2) for i in range(kSplineTableSize)
    ]

    def getTForX(aX):
        intervalStart = 0.0
        currentSample = 1
        lastSample = kSplineTableSize - 1

        while currentSample != lastSample and sampleValues[currentSample] <= aX:
            intervalStart += kSampleStepSize
            currentSample += 1
        currentSample -= 1

        # Interpolate to provide an initial guess for t
        dist = (aX - sampleValues[currentSample]) / (
            sampleValues[currentSample + 1] - sampleValues[currentSample]
        )
        guessForT = intervalStart + dist * kSampleStepSize

        initialSlope = getSlope(guessForT, mX1, mX2)
        if initialSlope >= NEWTON_MIN_SLOPE:
            return newtonRaphsonIterate(aX, guessForT, mX1, mX2)
        elif initialSlope == 0.0:
            return guessForT
        else:
            return binarySubdivide(
                aX, intervalStart, intervalStart + kSampleStepSize, mX1, mX2
            )

    def BezierEasing(x):
        if x == 0 or x == 1:
            return x
        return calcBezier(getTForX(x), mY1, mY2)

    return BezierEasing
