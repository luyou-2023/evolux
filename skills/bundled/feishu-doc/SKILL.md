---
name: feishu-doc
description: Feishu document and messaging workflows
metadata:
  domain: feishu
---
# Feishu Doc Skill

Use `feishu_doc_read`, `feishu_doc_create`, and `feishu_message` tools when working with Feishu documents and chats.

Bind credentials (scan / URL wizard):

```bash
evolux feishu setup --assistant default
# or: evolux assistant bind feishu --wizard --id default
```

Manual bind:

```bash
evolux assistant bind feishu --id default --app-id YOUR_APP --app-secret YOUR_SECRET
```
