# SeekR 1.1.0

## Highlights

### A redesigned Alt+Space launcher
- Reworked the launcher into a wider, balanced layout with the search results in the centre and two widget cards on each side.
- Added subtle widget entrance fades, animated launcher transitions, hover highlights, rounded surfaces and a restrained graphite-and-blue visual treatment.
- Increased the default launcher dimensions to give search results and widgets room to breathe.

### Four live widgets
- **Clock:** live local time and date.
- **System usage:** live CPU and memory usage with compact progress bars.
- **Weather:** current temperature, feels-like temperature and humidity for a city or town configured in Settings → Widgets. Weather lookups run off the UI thread and refresh every 30 minutes.
- **Daily meme:** a wholesome daily meme with a preview image and a link to the original post. The daily selection is cached locally and refreshed on the next calendar day.

All four widgets are enabled by default and can be individually enabled or disabled in Settings → Widgets. Weather and meme require an internet connection; the clock and system usage remain local. Weather uses the location text entered by the user and does not request device location permission.

### Search responsiveness
- Search execution remains off the GUI thread.
- The scheduler runs one search at a time and retains only the newest pending query, avoiding redundant intermediate work.
- Outdated results are ignored, preventing old searches from replacing the current query.

### Settings and configuration
- Added a dedicated Widgets settings page.
- Added a weather location field.
- Existing configuration files are automatically merged with the new defaults; existing user preferences are preserved.

## Notes
- Weather data is provided by Open-Meteo.
- Daily meme discovery uses the Meme API's wholesome-meme feed. Meme titles and preview images are cached in the local SeekR application-data folder.
- Network widgets show a useful unavailable state when the service cannot be reached.
- This release has not been manually validated on a physical Windows desktop in this development session. Run the repository's GitHub Actions checks and complete the Windows manual test checklist before treating the installer as production-verified.
