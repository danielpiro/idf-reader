# IDF Reader Website

🌐 Official website for IDF Reader - Professional IDF analysis software

## 🚀 Quick Deploy to Vercel

1. **Fork/Clone the repository**
2. **Connect to Vercel:**
   - Go to [vercel.com](https://vercel.com)
   - Import your GitHub repository
   - Select the `website` folder as root directory
3. **Deploy!** - Vercel will automatically build and deploy

## 📁 Project Structure

```
website/
├── index.html          # Main HTML file
├── styles.css          # CSS styles
├── script.js           # JavaScript functionality
├── vercel.json         # Vercel configuration
├── package.json        # NPM configuration
├── images/             # Image assets
│   ├── logo.png
│   ├── app-screenshot.png
│   └── preview.png
└── README.md          # This file
```

## 🛠️ Local Development

```bash
# Install Vercel CLI
npm i -g vercel

# Run locally
vercel dev

# Deploy to production
vercel --prod
```

## 🎨 Features

- ✅ **Responsive Design** - Works on all devices
- ✅ **Hebrew RTL Support** - Native right-to-left layout
- ✅ **Modern UI/UX** - Clean, professional design
- ✅ **GitHub Integration** - Auto-fetches latest releases
- ✅ **Contact Form** - Built-in contact functionality
- ✅ **SEO Optimized** - Meta tags, Open Graph, Twitter Cards
- ✅ **Performance** - Optimized loading and animations

## 🔧 Customization

### Update GitHub Repository
Edit the repository URL in `script.js`:
```javascript
const response = await fetch('https://api.github.com/repos/YOUR-USERNAME/YOUR-REPO/releases/latest');
```

### Update Contact Information
Edit contact details in `index.html`:
```html
<p>support@your-domain.com</p>
```

### Update Pricing
Modify pricing in the pricing section of `index.html`

### Add Analytics
Add Google Analytics or other tracking code in the `<head>` section

## 🌐 Domain Setup

### Custom Domain on Vercel
1. Go to your Vercel dashboard
2. Select your project
3. Go to Settings > Domains
4. Add your custom domain
5. Update DNS records as instructed

### DNS Configuration Example
```
Type: CNAME
Name: @
Value: cname.vercel-dns.com

Type: CNAME  
Name: www
Value: cname.vercel-dns.com
```

## 📈 Analytics & Tracking

The website includes:
- Download tracking
- Contact form submissions
- User engagement metrics
- Error tracking

To enable Google Analytics, uncomment and configure in `index.html`:
```html
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_TRACKING_ID"></script>
```

## 🖼️ Images Required

Create these images and place them in the `images/` folder:

1. **logo.png** (40x40px) - Website logo
2. **app-screenshot.png** (800x600px) - App screenshot for hero section  
3. **preview.png** (1200x630px) - Social media preview image
4. **favicon.ico** (32x32px) - Browser favicon

## 🚀 Performance Tips

- Images are optimized for web
- CSS and JS are minified for production
- Lazy loading for images below the fold
- CDN delivery through Vercel

## 📱 Mobile Optimization

- Responsive grid layouts
- Touch-friendly navigation
- Optimized font sizes
- Mobile-first design approach

## 🔍 SEO Features

- Semantic HTML structure
- Meta descriptions and keywords
- Open Graph tags for social sharing
- Twitter Card support
- Structured data markup ready

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally with `vercel dev`
5. Submit a pull request

## 📞 Support

For website issues or customization help:
- Create an issue on GitHub
- Email: support@your-domain.com

---

Built with ❤️ for the IDF Reader community