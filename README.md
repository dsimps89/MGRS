# Tactical Ops Planner — GitHub Pages Version

A browser-based tactical planning template converted from the uploaded Python tools.  
This version is designed for GitHub Pages and works on iPhone, iPad, Android, Mac, Windows, and desktop browsers.

## Files

```text
index.html                 Main app page
assets/css/styles.css      Visual styling
assets/js/app.js           App logic and local browser storage
assets/data/               Sample data and grid image
source-python/             Original Python files for reference
docs/                      Conversion notes
.nojekyll                  Keeps GitHub Pages from processing the site with Jekyll
404.html                   Redirect fallback
```

## How to publish on GitHub Pages from iPhone

1. Create a new GitHub repository.
2. Upload **all files inside this ZIP** to the repository root.
3. Open the repository on GitHub.
4. Go to **Settings**.
5. Go to **Pages**.
6. Under **Build and deployment**, choose:
   - **Source:** Deploy from a branch
   - **Branch:** main
   - **Folder:** /root
7. Tap **Save**.
8. Wait for GitHub to create your website link.

Your live site will usually look like:

```text
https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPOSITORY-NAME/
```

## Notes

- This app stores saved records in the browser using `localStorage`.
- Data saved on one device does not automatically sync to another device.
- This is a planning/template tool and should be reviewed before any real-world use.
