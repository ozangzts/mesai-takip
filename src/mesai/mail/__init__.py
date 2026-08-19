"""Choosing who a month's figures go to, and eventually sending them.

Only the choosing exists so far. It lives here rather than in the window for the reason
`ARCHITECTURE.md` §3 gives about `cli.py`: "who falls into this category, minus these
people" is a business rule, and a rule inside a widget cannot be tested. The window
displays what `recipients.py` decided and nothing more.

Nothing here sends anything yet. Three questions have to be answered first — whether
the default is a preview or a send, whether a hand-removed person is recorded, and
whether an incomplete month may be mailed at all — and none of them has been.
"""
