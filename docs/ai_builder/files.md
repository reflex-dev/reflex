# Files

To upload a file to the AI Builder click the `📎 Attach` button and select the file you want to upload from your computer. You can also drag and drop files directly into the chat window.

This section does not cover uploading images. Check out [Images](/docs/ai/images/) to learn more about uploading images.

```md alert
## Supported File Types
The AI Builder currently supports the following file types for upload and processing:
1. `.pdf`
2. `.doc`
3. `.docx`
4. `.xls`
5. `.xlsx`
6. `.ppt`
7. `.pptx`
8. `.odt`
9. `.ods`
10. `.odp`
11. `.rtf`
12. `.csv`
13. `.txt`
14. `.md`
15. `.markdown`
16. `.json`
17. `.xml`
18. `.yaml`
19. `.yml`
20. `.tsv`
```

The files you upload will automatically be added to the `assets/` folder of your app, and the AI Builder will be able to read and process their contents as part of your prompts.

The maximum number of files you can upload at a time is `5`. The maximum file size for uploads is `5MB`. If you need to work with larger files, consider breaking them into smaller chunks or using external storage solutions and linking to them via APIs.
