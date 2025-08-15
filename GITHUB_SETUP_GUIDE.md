# 🚀 GitHub Auto-Update Setup Guide

## Complete step-by-step guide for setting up auto-updates with your private GitHub repository

---

## 📋 **Prerequisites**

✅ Your repository: `https://github.com/danielpiro/idf-reader` (Private)  
✅ Auto-update system implemented  
✅ GitHub Actions workflow created  

---

## 🔧 **Step 1: Configure GitHub Repository**

### Enable GitHub Actions (if not already enabled)
1. Go to your repository: `https://github.com/danielpiro/idf-reader`
2. Click **Settings** tab
3. In the left sidebar, click **Actions** > **General**
4. Under "Actions permissions", select **"Allow all actions and reusable workflows"**
5. Click **Save**

### Configure Repository Secrets (if needed)
1. Go to **Settings** > **Secrets and variables** > **Actions**
2. The workflow uses `GITHUB_TOKEN` which is automatically provided
3. No additional secrets needed for basic functionality

---

## 🏗️ **Step 2: Create Your First Release**

### Method A: Using the Build Script (Recommended)

```bash
# Navigate to your project directory
cd "C:\Users\daniel\Desktop\idf-reader"

# Build and increment version
python build_with_version.py patch  # 1.0.0 -> 1.0.1

# Commit the version update
git add version.py
git commit -m "Bump version to 1.0.1"

# Create and push a version tag
git tag v1.0.1
git push origin main
git push origin v1.0.1
```

### Method B: Manual GitHub Release

1. Go to your repository on GitHub
2. Click **Releases** (right sidebar)
3. Click **Create a new release**
4. Tag version: `v1.0.1`
5. Release title: `גרסה 1.0.1`
6. Description: Add Hebrew release notes
7. Upload your `.exe` file if you have one
8. Click **Publish release**

---

## 🔑 **Step 3: Set Up GitHub Token for Users**

Since your repository is private, users need a GitHub token to check for updates.

### Create a Personal Access Token

1. **For YOU (the developer):**
   - Go to https://github.com/settings/tokens/new
   - Token name: `IDF-Reader-Updates`
   - Expiration: Choose appropriate duration
   - Scopes: Check **`repo`** (Full control of private repositories)
   - Click **Generate token**
   - **Copy the token immediately** (you won't see it again!)

2. **For USERS of your app:**
   - They need their own GitHub accounts
   - They need access to your private repository
   - They need to create their own tokens with `repo` scope

### Configure Token in the App

1. Run your application
2. Click the **⚙️** (update settings) button in the header
3. Click **"הגדר GitHub Token"**
4. Paste your token: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
5. Click **"שמור Token"**

---

## 🎯 **Step 4: Test the Auto-Update System**

### Test Update Detection

1. **Create a test release:**
   ```bash
   # Create version 1.0.2
   python build_with_version.py patch
   git add version.py
   git commit -m "Bump version to 1.0.2"
   git tag v1.0.2
   git push origin main
   git push origin v1.0.2
   ```

2. **Test in your app:**
   - Run the app with version 1.0.1
   - Click **⚙️** > **"בדוק עדכונים עכשיו"**
   - Should detect version 1.0.2 is available

### Test Full Update Flow

1. **Create a proper release with executable:**
   ```bash
   # Build the executable
   python build_with_version.py patch  # This creates the .exe file
   
   # The GitHub Action will automatically:
   # - Build the executable
   # - Create a release
   # - Upload the .exe file
   ```

2. **Verify the update works:**
   - App detects new version
   - Shows update dialog
   - Downloads and installs update
   - Restarts with new version

---

## 🔄 **Step 5: Automate Your Release Process**

### Option A: Automated Releases via Tags

```bash
# Every time you want to release:
python build_with_version.py patch  # or minor/major
git add version.py
git commit -m "Bump version to $(python -c "from version import get_version; print(get_version())")"
git tag v$(python -c "from version import get_version; print(get_version())")
git push origin main
git push origin --tags

# GitHub Actions will automatically:
# 1. Build the executable
# 2. Create a GitHub release
# 3. Upload the files
```

### Option B: Manual Trigger

1. Go to your repository
2. Click **Actions** tab
3. Click **"Build and Release"** workflow
4. Click **"Run workflow"**
5. Enter version number (e.g., `1.0.3`)
6. Click **"Run workflow"**

---

## 👥 **Step 6: Distribute to Users**

### For Users with GitHub Access

1. **Give them repository access:**
   - Go to your repo > **Settings** > **Manage access**
   - Click **Add people**
   - Add their GitHub usernames
   - Give them **Read** permission

2. **They need to configure GitHub token:**
   - They create their own token at https://github.com/settings/tokens/new
   - Scope: `repo` access
   - They enter it in your app via **⚙️** > **"הגדר GitHub Token"**

### For Users without GitHub Access

**Option 1: Make Repository Public**
- Go to **Settings** > **General** > **Danger Zone**
- Click **"Change repository visibility"** > **"Make public"**
- Users won't need tokens

**Option 2: Custom Update Server**
- Deploy your own update server (based on `update_server.py`)
- Host your `.exe` files on your own server
- Update `UPDATE_SERVER_URL` in `version.py`

---

## 🛠️ **Step 7: Production Configuration**

### Update version.py for Production

```python
# For GitHub releases (recommended for private repos with tokens)
UPDATE_SERVER_URL = ""  # Disable custom server
GITHUB_RELEASES_URL = "https://api.github.com/repos/danielpiro/idf-reader/releases/latest"

# OR for custom server (recommended for wider distribution)
UPDATE_SERVER_URL = "https://your-domain.com/api"  # Your production server
GITHUB_RELEASES_URL = ""  # Disable GitHub releases
```

### Security Considerations

1. **Token Security:**
   - Tokens are stored locally in app settings
   - Consider encryption for production
   - Set reasonable token expiration

2. **Update Verification:**
   - Consider adding file checksums
   - Digital signature verification
   - Staged rollouts for major updates

---

## 📊 **Monitoring and Analytics**

### Track Update Success

```bash
# Check your GitHub release download statistics
# Go to: https://github.com/danielpiro/idf-reader/releases
# View download counts for each release
```

### Debug Update Issues

1. **Enable debug logging** in your app
2. **Check network connectivity** 
3. **Verify GitHub token permissions**
4. **Check repository access**

---

## 🆘 **Troubleshooting Common Issues**

### "Authentication failed" or "API rate limit"
- ✅ Verify GitHub token is correct
- ✅ Check token has `repo` scope
- ✅ Ensure user has repository access

### "No releases found"
- ✅ Verify repository URL in `version.py`
- ✅ Check if releases exist on GitHub
- ✅ Ensure releases are not drafts

### "Download failed"
- ✅ Check internet connectivity
- ✅ Verify executable exists in release assets
- ✅ Check antivirus isn't blocking download

### "Installation failed"
- ✅ Run as administrator
- ✅ Close all app instances
- ✅ Check disk space and permissions

---

## ✅ **Verification Checklist**

- [ ] GitHub Actions workflow is working
- [ ] Can create releases via git tags
- [ ] GitHub token is configured in app
- [ ] Manual update check works
- [ ] Automatic update detection works
- [ ] Update dialog appears correctly
- [ ] Download and installation works
- [ ] App restarts with new version
- [ ] Users can access private repository
- [ ] Release notes display in Hebrew

---

## 🎉 **You're All Set!**

Your auto-update system is now fully configured with GitHub releases. Users will automatically receive notifications when new versions are available, and they can update with a single click.

**Next steps:**
1. Test with a few trusted users
2. Monitor download statistics
3. Gather feedback on the update experience
4. Consider automating version bumps in your development workflow