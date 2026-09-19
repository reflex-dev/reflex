# Verifier drive_quiz.py stdout (three installs, same script, same flows)

Script: `verification/drive_quiz.py` (unchanged copy of the explorer's
`scripts/drive_quiz.py`). Ports: new 4040/9040, prev 4041/9041, mixed 4042/9042.

`results` blocks were identical field-for-field across all three runs except the
`http://localhost:<port>` prefix in `url_after_submit` / `url_after_back`:

```
title                          Quiz - Reflex
heading                        Python Quiz
code_block_present             true
code_block_text                "a = [10, 20]\nb = a\nb += [30, 40]\nprint(a"
radio_count                    4
checkbox_count                 5
redirected                     true
shows_100                      true
score_text                     100%
table_rows                     3
checkboxes_checked_after_back  0
direct_result_title            Quiz Results
direct_result_has_results      true
console_errors                 []
page_errors                    []
failed_requests                []
bad_responses                  []
```

`console_warnings` in ALL THREE runs (identical text, exactly 3 entries each — one per
checkbox clicked):

```
Checkbox is changing from uncontrolled to controlled. Components should not switch from
controlled to uncontrolled (or vice versa). Decide between using a controlled or
uncontrolled value for the lifetime of the component.
```

Screenshots after the three checkbox clicks are byte-identical across all three installs:

```
ae68a21046d1217bb7073d28eef743c3  vquiz_new_02_answered.png     (reflex 0.9.12a1 + all component alphas)
ae68a21046d1217bb7073d28eef743c3  vquiz_prev_02_answered.png    (reflex 0.9.11.post1 + stable components)
ae68a21046d1217bb7073d28eef743c3  vquiz_mixed_02_answered.png   (reflex 0.9.12a1 core + STABLE components)
```
