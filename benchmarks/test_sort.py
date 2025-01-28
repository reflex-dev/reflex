import random


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


SORTED_ARRAY = list(range(1000))

SHUFFLED_ARRAY = SORTED_ARRAY[:]
random.shuffle(SHUFFLED_ARRAY)


def test_bubble_sort(benchmark):
    result = benchmark(bubble_sort, SHUFFLED_ARRAY)
    assert result == SORTED_ARRAY


def test_merge_sort(benchmark):
    result = benchmark(merge_sort, SHUFFLED_ARRAY)
    assert result == SORTED_ARRAY
