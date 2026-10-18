---
"@modelcontextprotocol/server-filesystem": patch
---

Overwrite an existing file again on Windows with Node 23. There a path-based `lstat` reports the device as 0 while the same file read through the opened handle reports the volume serial, and the in-place overwrite's identity check read that difference as a replaced file, so `write_file` and `edit_file` refused every overwrite with "was replaced while it was being opened" (#5154).
