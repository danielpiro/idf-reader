# Auto-Update System Documentation

## Overview

The IDF Reader application now includes an automatic update system that allows users to receive updates seamlessly when new versions are released.

## Features

- **Automatic Update Checking**: Checks for updates in the background based on user preferences
- **Manual Update Checking**: Users can manually check for updates via the GUI
- **Version Comparison**: Smart version comparison to determine if updates are available
- **Download & Install**: Automatic download and installation of updates
- **Restart Management**: Handles application restart after updates
- **Settings Management**: Configurable update preferences

## Files Added/Modified

### New Files:
- `version.py` - Version management and configuration
- `utils/update_manager.py` - Core update functionality
- `update_server.py` - Development/testing update server
- `build_with_version.py` - Enhanced build script with versioning

### Modified Files:
- `modern_gui.py` - Added update GUI integration

## Usage

### For Users

1. **Automatic Updates**: Updates are checked automatically when the app starts (if enabled)
2. **Manual Check**: Click the update button (⚙️) in the header to check manually
3. **Update Notification**: When an update is available, a dialog will appear with:
   - Current version vs new version
   - Release notes
   - Options to install now, remind later, or dismiss

### For Developers

#### Building with Version Management

```bash
# Increment patch version (1.0.0 -> 1.0.1)
python build_with_version.py patch

# Increment minor version (1.0.0 -> 1.1.0) 
python build_with_version.py minor

# Increment major version (1.0.0 -> 2.0.0)
python build_with_version.py major

# Set custom version
python build_with_version.py custom 1.5.0
```

#### Testing Update System

1. **Start the test update server**:
   ```bash
   python update_server.py 8000
   ```

2. **Run the application** - it will check the local server for updates

3. **Simulate an update**:
   - Edit `update_server.py` to return a higher version number
   - The app will detect and offer the update

#### Deployment Options

##### Option 1: GitHub Releases
1. Create releases on GitHub with version tags (e.g., `v1.1.0`)
2. Attach the executable as a release asset
3. Update `GITHUB_RELEASES_URL` in `version.py` with your repository

##### Option 2: Custom Update Server
1. Deploy your own update server (based on `update_server.py`)
2. Update `UPDATE_SERVER_URL` in `version.py`
3. Host your update files and version information

## Configuration

### Update Settings

Users can configure update behavior through the GUI:
- **Auto-check**: Enable/disable automatic update checking
- **Check interval**: How often to check (default: 24 hours)
- **Update channel**: stable, beta, alpha (for future use)

Settings are stored in `update_settings.json`:
```json
{
    "auto_check": true,
    "check_interval_hours": 24,
    "last_check": 1704123456,
    "update_channel": "stable",
    "download_timeout": 300
}
```

## Security Considerations

1. **HTTPS**: Always use HTTPS for production update servers
2. **Signature Verification**: Consider adding digital signature verification for update files
3. **Checksum Validation**: Implement checksum validation for downloaded files
4. **Staged Rollouts**: Consider implementing staged rollouts for major updates

## API Endpoints

### Check for Updates
```
GET /api/check_update?current_version=1.0.0&channel=stable&platform=win32
```

Response:
```json
{
    "update_available": true,
    "version": "1.1.0",
    "download_url": "https://server.com/downloads/app-1.1.0.exe",
    "release_notes": "• Feature improvements\n• Bug fixes",
    "file_size": 52428800,
    "checksum": "sha256:abc123...",
    "required": false,
    "release_date": "2024-01-15T10:30:00Z"
}
```

### Download Update
```
GET /api/download?version=1.1.0&platform=win32
```

Returns the binary file for download.

## Error Handling

The update system includes comprehensive error handling for:
- Network connectivity issues
- Server unavailability
- Corrupted downloads
- Installation failures
- Permission issues

All errors are logged and displayed to the user with appropriate Hebrew messages.

## Future Enhancements

1. **Delta Updates**: Only download changed files instead of full application
2. **Rollback**: Ability to rollback to previous version if issues occur
3. **Update Scheduling**: Allow users to schedule updates for specific times
4. **Bandwidth Management**: Throttle download speed to not interfere with other activities
5. **Update History**: Keep track of update history and changelog

## Troubleshooting

### Common Issues

1. **Update check fails**: 
   - Check internet connection
   - Verify update server URL in `version.py`
   - Check firewall/antivirus settings

2. **Download fails**:
   - Check available disk space
   - Verify write permissions
   - Check for antivirus interference

3. **Installation fails**:
   - Run as administrator if needed
   - Close other instances of the application
   - Check for file locks

### Debug Mode

Enable debug logging by setting the log level to DEBUG to see detailed update process information.

## Testing Checklist

- [ ] Manual update check works
- [ ] Automatic update check works
- [ ] Update dialog displays correctly
- [ ] Download progress shows properly
- [ ] Installation completes successfully
- [ ] Application restarts after update
- [ ] Version number updates correctly
- [ ] Settings are preserved after update
- [ ] Error handling works for network issues
- [ ] Error handling works for invalid versions