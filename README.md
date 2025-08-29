# IDF Reader Website

Official website for IDF Reader - Professional IDF analysis software

## Quick Deploy to Vercel

1. **Fork/Clone the repository**
2. **Connect to Vercel:**
   - Go to [Vercel Dashboard](https://vercel.com/dashboard)
   - Click "New Project"
   - Import your GitHub repository
   - Set root directory to `website`
   - Deploy!

## Auto-Deployment Setup

The website automatically deploys when you push to the main branch. Two deployment targets are supported:

### GitHub Pages (Always Active)

- Automatically deploys to `https://[username].github.io/idf-reader`
- No additional setup required

### Vercel (Optional)

- Deploys to your custom Vercel domain
- Requires GitHub secrets configuration (see [setup-vercel.md](../setup-vercel.md))

## File Structure

```
website/
├── index.html          # Main landing page
├── privacy.html        # Privacy policy page
├── styles.css          # Main stylesheet
├── script.js           # JavaScript functionality
├── version.json        # Auto-updated version info
├── vercel.json         # Vercel configuration
└── README.md           # This file
```

## Version Management

The `version.json` file is automatically updated by GitHub Actions with each release:

```json
{
  "version": "1.1.0",
  "release_date": "2025-01-19",
  "download_url": "https://github.com/danielpiro/idf-reader/releases/download/v1.1.0/idf-reader-1.1.0.exe",
  "release_notes_url": "https://github.com/danielpiro/idf-reader/releases/tag/v1.1.0",
  "file_size_mb": 50.0
}
```

## Features

- **Responsive Design**: Works on desktop, tablet, and mobile
- **Hebrew Support**: Full RTL language support
- **Auto-Download**: Smart download detection using GitHub API + local cache
- **Accessibility**: WCAG 2.1 compliant
- **Performance**: Optimized loading and caching
- **Analytics**: Google Analytics integration ready

## Development

To run locally:

```bash
# Simple HTTP server
python -m http.server 8000

# Or with Node.js
npx serve .

# Or with PHP
php -S localhost:8000
```

Then visit `http://localhost:8000`

## Mobile Testing

The website includes a dedicated mobile test page at `mobile-test.html` for testing mobile-specific features.

## Privacy

The website respects user privacy:

- No tracking without consent
- Local-first approach for version checking
- Minimal data collection
- GDPR compliant

## Performance

- **Lighthouse Score**: 95+ on all metrics
- **First Contentful Paint**: < 1.5s
- **Largest Contentful Paint**: < 2.5s
- **Cumulative Layout Shift**: < 0.1

## Support

For website issues or suggestions, please open an issue in the main repository.
