{#- towncrier's default Markdown template, plus one case: an entry that ends in
    a fenced code block gets its issue links after the prose, above the block,
    where the default appends them to the closing fence. -#}
{%- macro heading(level) -%}
    {{- "#" * ( header_prefix | length + level -1 ) }}
{%- endmacro -%}
{%- set newline = "\n" -%}
{#- render_title is false when title_format is set in the config #}
{%- if render_title %}
    {%- if versiondata.name %}
        {{- heading(1) ~ " " ~ versiondata.name ~ " " ~ versiondata.version ~ " (" ~ versiondata.date ~ ")" ~ newline }}
    {%- else %}
        {{- heading(1) ~ " " ~ versiondata.version ~ " (" ~ versiondata.date ~ ")" ~ newline }}
    {%- endif %}
{%- endif %}
{{- newline }}

{%- for section, _ in sections.items() %}
    {%- if section %}
        {{- newline }}
        {{- heading(2) ~ " " ~ section ~ newline }}
        {{- newline }}
    {%- endif %}

    {%- if sections[section] %}

        {%- for category, val in definitions.items() if category in sections[section] %}
            {%- set issue_pks = [] %}
            {{- heading(3 if section else 2) ~" " ~ definitions[category]['name'] ~ newline }}
            {{- newline }}

            {%- for text, values in sections[section][category].items() %}
                {%- set issue_pks = [] %}
                {%- for v_issue in values %}
                    {%- set _= issue_pks.append(v_issue.split(": ", 1)[0]) %}
                {%- endfor %}
                {%- set issues_list = issue_pks | join(", ") %}

                {%- set text_has_sublist = (("\n  - " in text) or ("\n  * " in text)) %}

                {#- Walk the fenced blocks as CommonMark does: a run of three or
                    more backticks or tildes opens one, and a line of only that
                    character, at least as long, closes it. ns.cut is the index
                    of the opener when the last line closes a block. #}
                {%- set lines = text.split("\n") %}
                {%- set ns = namespace(open=none, start=none, cut=none) %}
                {%- for line in lines %}
                    {%- set s = line.strip() %}
                    {%- if ns.open is none %}
                        {#- A backtick info string can't hold a backtick. #}
                        {%- if s[:3] == "~~~" or (s[:3] == "```" and "`" not in s.lstrip("`")) %}
                            {%- set ns.open = s[0] * (s | length - s.lstrip(s[0]) | length) %}
                            {%- set ns.start = loop.index0 %}
                        {%- endif %}
                    {%- elif s.startswith(ns.open) and s.count(s[0]) == s | length %}
                        {%- set ns.open = none %}
                        {%- set ns.cut = ns.start if loop.last else none %}
                    {%- endif %}
                {%- endfor %}
                {%- set prose = lines[:ns.cut] | join("\n") | trim if ns.cut else "" %}
                {#- Prose that itself ends in a code block can't take the links. #}
                {%- set last = prose.split("\n")[-1].strip() %}
                {%- set prose_ends_in_fence = last[:3] in ("```", "~~~") and last.count(last[0]) == last | length %}

                {%- if not text and issues_list %}
                    {#- Only issues: -  #1, #9, #142 #}
                    {{- "- " ~ issues_list ~ newline }}
                {%- elif text and issues_list %}
                    {%- if text_has_sublist or (ns.cut is not none and (not prose or prose_ends_in_fence)) %}
                        {#- Sublist, or a code block with no prose before it:
                            - TEXT\n\n  (#1, #9, #142) #}
                        {{- "- " ~ text ~ newline ~ newline ~ "  (" ~ issues_list ~ ")" ~ newline }}
                    {%- elif ns.cut is not none %}
                        {#- Prose then a code block: - PROSE (#1, #9, #142)\n\n  CODE #}
                        {{- "- " ~ prose ~ " (" ~ issues_list ~ ")" ~ newline ~ newline ~ lines[ns.cut:] | join("\n") ~ newline }}
                    {%- else %}
                        {#- - TEXT (#1, #9, #142) #}
                        {{- "- " ~ text ~ " (" ~ issues_list ~ ")" ~ newline }}
                    {%- endif %}
                {%- elif text %}
                    {{- "- " ~ text ~ newline }}
                {%- endif %}
            {%- endfor %}

            {{- newline }}

            {%- if issues_by_category[section][category] and "]: " in issues_by_category[section][category][0] %}
                {%- for issue in issues_by_category[section][category] %}
                    {{- issue ~ newline }}
                {%- endfor %}
                {{- newline }}
            {%- endif %}

            {%- if sections[section][category]|length == 0 %}
                {{- newline }}
                {{- "No significant changes." ~ newline * 2 }}
            {%- endif %}
        {%- endfor %}
    {%- else %}
        {{- "No significant changes." ~ newline * 2 }}
    {%- endif %}
{%- endfor %}
{#- Two newlines between the newest release and the previous content. -#}
{{- newline -}}
