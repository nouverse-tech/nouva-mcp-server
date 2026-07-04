# Guidelines for Contributing to gading.dev

Follow this workflow and standards to add or update content in the `gading.dev` repository.

## Directory Structure
- **Indonesian Posts**: `src/contents/posts/id/` (.md / .mdx)
- **English Posts**: `src/contents/posts/en/` (.md / .mdx)
- **Media Assets**: `public/media/blog/<slug>/`

## Frontmatter Schema
Every post must contain this exact YAML frontmatter structure:
```yaml
---
title: "Post Title"
slug: 
  en: "english-slug"
  id: "indonesian-slug"
date: YYYY-MM-DD
description: "SEO summary"
keywords: "key, words"
tags: ["tag1", "tag2"]
image: "/media/blog/<slug>/banner.png" # or "/media/default-banners/X.jpg"
---
```

## Content Standards
- **Language**: Support both `id` and `en`. Always provide a slug mapping for both languages.
- **Media**: Banner image is mandatory. Place images in `public/media/blog/<slug>/`.
- **Formatting**: Use GFM (GitHub Flavored Markdown) and MDX components where appropriate.

## Writing Style ("Engineering Scars")
When writing or rewriting posts, emulate Gading's authentic engineering style:
- **Focus on the "Why" and "Why Not"**: Focus heavily on decision-making. Explain why a choice was made and what was rejected.
- **Show the Messy Progress**: Write as a journey. Show changes of mind (e.g., "gue install -> setelah dipake ternyata overkill -> gue uninstall"), trade-offs, failures, and how problems were actually solved.
- **Casual & Unstructured Flow**: Keep it natural, conversational, and slightly unstructured. Use casual warkop-style language ("gw/lu", "anjir", "kejedut", "rollback") and humor. Avoid clean/perfect AI structures and corporate buzzwords ("scalable", "robust", "efficient").

## Publishing Workflow
Setelah menulis draft artikel di workspace, jalankan alur berikut:
1. Panggil tool `gading_dev_review` untuk membuat branch dan Pull Request (PR) ke repo `gading.dev`.
2. Setelah disetujui (approved), jalankan tool `gading_dev_publish` untuk meng-merge PR tersebut ke branch `main` dan otomatis mentrigger workflow sync Cloudinary.

