# 🚌 Transperth Bus Times for Home Assistant

Real-time Perth public transport information in your Home Assistant dashboard. Get live bus departure times, stop information, and journey details from Transperth directly in your smart home.

## 🚀 Getting Started (5 minutes)

### Prerequisites
- Home Assistant with HACS installed
- File access to your Home Assistant config folder (via Samba, File Editor, or SSH)

### Step 1: Install PyScript via HACS

1. Open HACS in your Home Assistant
2. Click **Integrations** → **Explore & Download Repositories**
3. Search for **"PyScript"**
4. Click **Download** → **Download** (use latest version)
5. Restart Home Assistant
6. Go to **Settings** → **Devices & Services** → **Add Integration**
7. Search for **"PyScript"** and click it
8. Click **Submit** (keep "Allow all imports" checked)

### Step 2: Install the Bus Times Service

1. Download the service file from this repository
   - Copy `src/transperth_bus_times/__init__.py`

2. Place the file in your Home Assistant config:
   ```
   config/
   └── pyscript/
       └── apps/
           └── bus_times/
               └── __init__.py  ← Put the file here
   ```
   
   **Note:** You may need to create the `pyscript/apps/bus_times/` folders

3. Reload PyScript:
   - Go to **Developer Tools** → **Services**
   - Search for `pyscript.reload`
   - Click **Call Service**

### Step 3: Test It Works

1. Go to **Developer Tools** → **Services**
2. Search for `pyscript.get_bus_stops`
3. Enter this YAML:
   ```yaml
   bus_number: "209"
   ```
4. Click **Call Service**
5. You should see bus times in the response!


## 🎯 Features

- **🚌 Real-time Departures** - Get the next bus times for any route
- **🗺️ Complete Routes** - See all stops for any bus journey
- **⏰ Stop Schedules** - Find when buses arrive at your stop
- **📍 Direction Support** - Handle inbound/outbound routes correctly
- **❤️ Health Check** - Monitor if the service is working


## 📖 Available Services

### `pyscript.get_bus_stops`
Shows all stops for the next bus on a route.

**Example:**
```yaml
service: pyscript.get_bus_stops
data:
  bus_number: "950"
  direction: "both"  # Optional: both (default), inbound, or outbound
```

**Returns:** Complete journey with all stops, times, and GPS coordinates

### `pyscript.get_bus_times` 
Shows all times a specific bus arrives at a specific stop today.

**Example:**
```yaml
service: pyscript.get_bus_times
data:
  bus_number: "209"
  stop_code: "10001"  # Find stop codes at transperth.wa.gov.au
  direction: "both"    # Optional
```

**Returns:** List of all arrival times at that stop

### `pyscript.bus_times_health_check`
Checks if the integration is working.

**Example:**
```yaml
service: pyscript.bus_times_health_check
```

**Returns:** Status of API connection and authentication

## 🏠 Home Assistant Automations

### Morning Commute Reminder
```yaml
automation:
  - alias: "Morning Bus Alert"
    trigger:
      - platform: time
        at: "07:30:00"
    action:
      - service: pyscript.get_bus_stops
        data:
          bus_number: "950"
        response_variable: bus_info
      - service: notify.mobile_app_your_phone
        data:
          title: "🚌 Time to leave!"
          message: >
            Next 950 bus departs at {{ bus_info.departure_time }}.
            Arrives city at {{ bus_info.arrival_time }}.
```


## 🔍 Finding Stop Codes

Stop codes are the numbers on Transperth bus stop signs. To find them:

1. Visit [transperth.wa.gov.au](https://www.transperth.wa.gov.au)
2. Use the Journey Planner
3. Click on any stop to see its code
4. Or look at the physical bus stop sign

Common Perth stop codes:
- Perth Busport: Various (10xxx range)
- Perth Underground: 10351
- Elizabeth Quay Bus Stn: Multiple platforms (11xxx range)

## 🛠️ Troubleshooting

### Services Not Appearing
- **Check PyScript is running:** Settings → Devices & Services → PyScript should show "Connected"
- **Check the file location:** Must be in `config/pyscript/apps/bus_times/__init__.py`
- **Check logs:** Settings → System → Logs → Search for "pyscript"
- **Reload PyScript:** Developer Tools → Services → `pyscript.reload`

### No Bus Data Returned
- **Check bus number:** Ensure it's a valid Transperth route (e.g., "950", "209", not "Bus950")
- **Check stop code:** Must be the exact number from the stop sign
- **Run health check:** Call `pyscript.bus_times_health_check` service
- **API might be down:** Check if [transperth.wa.gov.au](https://www.transperth.wa.gov.au) is working

### Wrong Direction Data
- Try setting `direction: "both"` to automatically detect the correct direction
- Some routes only run in one direction at certain times


## 📚 References

- **PyScript Documentation:** [hacs-pyscript.readthedocs.io](https://hacs-pyscript.readthedocs.io/)
- **PyScript GitHub:** [github.com/custom-components/pyscript](https://github.com/custom-components/pyscript)
- **Transperth Website:** [transperth.wa.gov.au](https://www.transperth.wa.gov.au)
- **Home Assistant Services:** [home-assistant.io/docs/scripts/service-calls](https://www.home-assistant.io/docs/scripts/service-calls/)
- **HACS Documentation:** [hacs.xyz](https://hacs.xyz/)

## 🔧 For Developers

### Project Structure
```
transperth_bus_times/
├── src/transperth_bus_times/
│   └── __init__.py          # Main PyScript service (copy this to HA)
├── tests/                   # Integration tests
├── docs/                    # Additional documentation
├── pyproject.toml          # Python project configuration
└── requirements.txt        # Dependencies (for development)
```

### Running Tests
```bash
# Clone the repository
git clone <repository-url>
cd transperth_bus_times

# Install dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Check code quality
ruff check src/
black src/
```

### How It Works
The service uses Transperth's internal API (same as their website) to fetch real-time data. It:
1. Authenticates using session tokens from the public website
2. Queries the SilverRail API endpoints for timetable data
3. Handles direction detection automatically
4. Returns structured data for Home Assistant

## 📝 Version History

- **1.0.0** - Initial release with two main services and health check

## ⚖️ Disclaimer

This is an unofficial integration that uses Transperth's public website API. Please:
- Use responsibly and don't overload their servers
- Respect Transperth's terms of service
- Understand this may stop working if Transperth changes their website
- Consider using official APIs if/when they become available

## 🤝 Contributing

Contributions welcome! Please:
1. Test your changes with real bus data
2. Update documentation if adding features
3. Follow the existing code style

## 💬 Support

- **Discussions:** [Home Assistant Community](https://community.home-assistant.io/)
- **PyScript Help:** [PyScript Discord](https://discord.gg/ND4emRS)

## 🙏 Acknowledgments

- Thanks to the PyScript developers for making Python automations possible in Home Assistant
- Thanks to Transperth for providing public transport services in Perth
- Thanks to the Home Assistant community for inspiration and support

---

*Made with ❤️ in Perth, Western Australia*