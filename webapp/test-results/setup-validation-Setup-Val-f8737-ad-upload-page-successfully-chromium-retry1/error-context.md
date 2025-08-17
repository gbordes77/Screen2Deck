# Page snapshot

```yaml
- alert
- dialog:
  - heading "Build Error" [level=1]
  - paragraph: Failed to compile
  - text: Next.js (14.2.5) is outdated
  - link "(learn more)":
    - /url: https://nextjs.org/docs/messages/version-staleness
  - link "./app/page.tsx:3:1":
    - text: ./app/page.tsx:3:1
    - img
  - text: "Module not found: Can't resolve '@/lib/api' 1 | 'use client'; 2 | import { useState } from 'react'; > 3 | import { upload } from '@/lib/api'; | ^ 4 | import { useRouter } from 'next/navigation'; 5 | export default function Page() { 6 | const [file, setFile] = useState<File| null>(null);"
  - link "https://nextjs.org/docs/messages/module-not-found":
    - /url: https://nextjs.org/docs/messages/module-not-found
  - contentinfo:
    - paragraph: This error occurred during the build process and can only be dismissed by fixing the error.
```