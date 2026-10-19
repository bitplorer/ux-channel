# html5lib intake

Runtime dependency of the strict morph/swap/toast stripper only.
`morph_html_policy="off"` does not import it.

| Field | Value |
| --- | --- |
| Requirement | `html5lib>=1.1,<2` |
| Installed | 1.1 |
| License | MIT |
| Last release | 2020-06-22 (1.1) |
| Why it is here | The standard library has no HTML5 tree builder that implements foreign content. svg and math need that, and `scripting=True` is what makes `noscript` raw text. |
| Transitive runtime deps | `six` 1.17.0 (MIT), `webencodings` 0.6.1 (BSD). No other package was added. html5lib extras (`lxml`, `genshi`, `chardet`) are not used. |
| Maintenance | Last release 2020-06-22. Tracked as a dependency to watch. The import sits inside `strip_dangerous_html` with that comment. |

## Alternatives rejected

| Alternative | Why not |
| --- | --- |
| `html.parser` | Not an HTML5 parser. It does not build foreign content (svg/math) the way a browser does, so the raw-text elements the stripper has to drop stay wrong. |
| lxml / libxml2 | Not HTML5 tokenization. |
| Beautiful Soup | Its HTML5 backend is html5lib, so it does not replace this dependency. |
| selectolax / lexbor | C extension. |
| gumbo / html5-parser | Unmaintained C bindings. |

## pip-audit

Command, against the pinned versions and their tree:

```text
uvx pip-audit -r requirements.txt
# html5lib==1.1
# six==1.17.0
# webencodings==0.6.1
```

Output (2026-10-19):

```text
No known vulnerabilities found
```

No known CVEs on html5lib 1.1, six 1.17.0, or webencodings 0.6.1.
