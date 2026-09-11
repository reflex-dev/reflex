# Cluster: memo_hash — #6947, clearing the auto-memoization naming caches

> Clear auto-memoization naming caches after compiling app.

A cache cleared between compiles has one obvious failure mode: **two apps compiled in the same
Python process**, which is what happens in a pytest session with more than one `AppHarness`, or in
any tool that builds several apps in one interpreter. If the naming cache leaked or was cleared at
the wrong moment, the second app could reuse a name the first app already emitted, and render the
first app's markup.

`test_memo_cache.py` builds exactly that. Two `AppHarness` apps, created one after the other in a
single pytest process, each defining an `rx.memo` component **with the same function name** `card`
and a different body (`ONE-{v}` vs `TWO={v}!`), each used inside an `rx.foreach` over a state list
so the auto-memoization path is exercised too. The assertions read the compiled output out of each
harness's `.web` tree rather than the served HTML — the memo body is compiled JavaScript and never
appears in the SSR document.

```
uv pip install --prerelease=allow 'reflex[testing]==0.9.11a1'
pytest test_memo_cache.py -q -s
```

## Result: 5 passed, no leakage

```
app_one memo names: ['Bare_comp_775db053..._aa63a4fa', 'Button_button_cbd972e5..._aa63a4fa',
                     'Card_aa63a4fa', 'DefaultOverlayComponents_04c36749',
                     'Errorboundary_errorboundary_31a7648b...',
                     'Foreach_comp_9932fd49..._aa63a4fa', 'MemoizedToastProvider_18b15038']
app_two memo names: ['Bare_comp_89d2f0fe..._964d7cb0', 'Button_button_306e95ab..._964d7cb0',
                     'Card_964d7cb0', 'DefaultOverlayComponents_04c36749',
                     'Errorboundary_errorboundary_31a7648b...',
                     'Foreach_comp_c959881e..._964d7cb0', 'MemoizedToastProvider_18b15038']
```

Exactly the right shape: the two same-named user memos get distinct names (`Card_aa63a4fa` vs
`Card_964d7cb0`), each app's auto-memoized `Foreach`/`Bare`/`Button` wrappers carry that app's own
suffix, and the components whose definitions really are identical across apps — the error boundary,
the toast provider, the default overlay — keep one shared name, which is what makes the cache worth
having. The first app's compiled output is unchanged after the second app compiles, and both
frontends still answer 200.

`peek.py` is the throwaway used to find where memo components actually land
(`.web/app_components/<appname>/<appname>.jsx`, not `.web/app/`).

## Findings raised

None.
