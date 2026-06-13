---
name: feishu-doc
description: Feishu document and messaging workflows
metadata:
  domain: feishu
---
# Feishu Doc Skill

When the user asks to **integrate / bind / connect Feishu** in CLI chat:

1. Call **`feishu_setup`** tool (mode=`shared_hermes` if Hermes gateway runs, else `auto`)
2. Or tell them to run **`/feishu setup`** in `evolux chat` (opens scan/URL in terminal)

After credentials exist, use `feishu_message`, `feishu_doc_read`, `feishu_doc_create`, `feishu_doc_append`.

Manual CLI:

```bash
evolux feishu setup --assistant default --mode shared_hermes
```
