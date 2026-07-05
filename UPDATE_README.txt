UPDATE BUNDLE - preserves history (no data/ folder). OVERFLOW ROOT-CAUSE FIX (dashboard/index.html, one line).
The previous wrapping fix was incomplete: the .asof caption class - used for nearly every
long caption on the page (review header lines, ledger driver lines, scout footers, long
as-of strings) - carried white-space:nowrap, which forbids line breaks entirely and
overrides overflow-wrap. That class now wraps normally. Short trend chips keep nowrap.
This should catch the remaining text running past section borders; if any specific spot
still overflows after this, name it and it gets fixed individually.
APPLY: upload dashboard/ only. No src, config, or workflow change.
