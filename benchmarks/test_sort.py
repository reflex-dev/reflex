import random

import pytest


def bubble_sort(arr: list[int]) -> list[int]:
    result = arr[:]
    for _ in range(len(result)):
        for j in range(len(result) - 1):
            if result[j] > result[j + 1]:
                result[j], result[j + 1] = result[j + 1], result[j]
    return result


def merge(sorted_left: list[int], sorted_right: list[int]) -> list[int]:
    result = []
    left = right = 0
    while left < len(sorted_left) and right < len(sorted_right):
        if sorted_left[left] < sorted_right[right]:
            result.append(sorted_left[left])
            left += 1
        else:
            result.append(sorted_right[right])
            right += 1
    result.extend(sorted_left[left:])
    result.extend(sorted_right[right:])
    return result


def merge_sort(arr: list[int]) -> list[int]:
    if len(arr) <= 1:
        return arr
    left = merge_sort(arr[: len(arr) // 2])
    right = merge_sort(arr[len(arr) // 2 :])
    return merge(left, right)


def sorted_and_shuffled_array(n: int) -> tuple[list[int], list[int]]:
    sorted_array = list(range(n))
    shuffled_array = sorted_array[:]
    random.shuffle(shuffled_array)
    return sorted_array, shuffled_array


def helper_test_sort(sort_func, benchmark, n):
    sorted_array, shuffled_array = sorted_and_shuffled_array(n)
    result = benchmark(sort_func, shuffled_array)
    assert result == sorted_array


sizes = [10, 100, 1000]


@pytest.mark.parametrize("n", sizes)
def test_bubble_sort(benchmark, n):
    helper_test_sort(bubble_sort, benchmark, n)


@pytest.mark.parametrize("n", sizes)
def test_merge_sort(benchmark, n):
    helper_test_sort(merge_sort, benchmark, n)


@pytest.mark.parametrize("n", sizes)
def test_builtin_sort(benchmark, n):
    helper_test_sort(sorted, benchmark, n)
