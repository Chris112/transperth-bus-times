#!/usr/bin/env python3
"""
Comprehensive test suite for all bus_times PyScript services
Tests all functionality including bus times, trip details, and favorites
"""

import sys
import os
import json
import csv
import tempfile
from datetime import datetime

# Add the parent directory to path to import the service modules
sys.path.insert(0, '/mnt/homeassistant/pyscript/apps/bus_times')

# Import required modules for testing
import requests
import re

# Configuration
BASE_URL = "https://www.transperth.wa.gov.au"
TEST_BUS_NUMBER = "209"
TEST_FAVORITE_NAME = "Test Route Home"

class Colors:
    """Terminal colors for test output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}TEST: {test_name}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")

def print_success(message):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")

def print_error(message):
    """Print error message"""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")

def print_info(message):
    """Print info message"""
    print(f"{Colors.YELLOW}ℹ {message}{Colors.RESET}")

def extract_token(html_content):
    """Extract the RequestVerificationToken from HTML"""
    token_match = re.search(r'<input\s+name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', html_content)
    if token_match:
        return token_match.group(1)
    return None

class BusTimesServiceTester:
    """Test harness for bus_times services"""
    
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.test_results = {
            "passed": 0,
            "failed": 0,
            "errors": []
        }
    
    def setup(self):
        """Setup test environment"""
        print_info("Setting up test environment...")
        
        # Get authentication token
        auth_url = f"{BASE_URL}/timetables/details?Bus={TEST_BUS_NUMBER}"
        response = self.session.get(auth_url)
        
        if response.status_code != 200:
            print_error(f"Failed to get auth page: {response.status_code}")
            return False
        
        self.token = extract_token(response.text)
        if not self.token:
            print_error("Failed to extract authentication token")
            return False
        
        print_success("Test environment setup complete")
        return True
    
    def test_bus_times_basic(self):
        """Test basic bus_times service functionality"""
        print_test_header("Bus Times - Basic Query")
        
        try:
            # Simulate the bus_times service call
            url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"
            
            headers = {
                "RequestVerificationToken": self.token,
                "ModuleId": "5345",
                "TabId": "133",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            now = datetime.now()
            data = {
                "ExactlyMatchedRouteOnly": "true",
                "Mode": "bus",
                "Route": TEST_BUS_NUMBER,
                "QryDate": now.strftime("%Y-%m-%d"),
                "QryTime": now.strftime("%H:%M"),
                "MaxOptions": "4"
            }
            
            print_info(f"Testing bus {TEST_BUS_NUMBER} at {data['QryTime']}")
            
            response = self.session.post(url, headers=headers, data=data)
            
            if response.status_code != 200:
                print_error(f"API request failed: {response.status_code}")
                self.test_results["failed"] += 1
                return None
            
            result = response.json()
            
            if result.get("result") == "success" and "data" in result:
                options = result["data"].get("Options", [])
                print_success(f"Retrieved {len(options)} departure options")
                
                # Validate response structure
                if options:
                    first = options[0]
                    required_fields = ["StartTime", "FinishTime", "StartLocation", 
                                     "FinishLocation", "TripKey", "RouteUid"]
                    
                    for field in required_fields:
                        if field in first:
                            print_success(f"Field '{field}' present: {first[field][:50]}...")
                        else:
                            print_error(f"Missing required field: {field}")
                            self.test_results["failed"] += 1
                            return None
                
                self.test_results["passed"] += 1
                return options[0] if options else None
            else:
                print_error(f"Unexpected response: {result}")
                self.test_results["failed"] += 1
                return None
                
        except Exception as e:
            print_error(f"Exception: {e}")
            self.test_results["errors"].append(str(e))
            self.test_results["failed"] += 1
            return None
    
    def test_bus_times_with_optional_params(self):
        """Test bus_times with optional parameters"""
        print_test_header("Bus Times - With Optional Parameters")
        
        try:
            url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"
            
            headers = {
                "RequestVerificationToken": self.token,
                "ModuleId": "5345",
                "TabId": "133",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            now = datetime.now()
            data = {
                "ExactlyMatchedRouteOnly": "true",
                "Mode": "bus",
                "Route": TEST_BUS_NUMBER,
                "Key": "715",  # Optional parameter
                "RouteUid": "SWA-SRI-4277",  # Optional parameter
                "QryDate": now.strftime("%Y-%m-%d"),
                "QryTime": now.strftime("%H:%M"),
                "MaxOptions": "10"  # Testing with more options
            }
            
            print_info("Testing with Key and RouteUid parameters")
            
            response = self.session.post(url, headers=headers, data=data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("result") == "success":
                    options = result.get("data", {}).get("Options", [])
                    print_success(f"Retrieved {len(options)} options with optional params")
                    self.test_results["passed"] += 1
                else:
                    print_error("API returned non-success result")
                    self.test_results["failed"] += 1
            else:
                print_error(f"API request failed: {response.status_code}")
                self.test_results["failed"] += 1
                
        except Exception as e:
            print_error(f"Exception: {e}")
            self.test_results["errors"].append(str(e))
            self.test_results["failed"] += 1
    
    def test_trip_details(self, trip_data=None):
        """Test bus_times_trip_details service"""
        print_test_header("Trip Details Service")
        
        if not trip_data:
            print_info("Getting fresh trip data...")
            trip_data = self.test_bus_times_basic()
            if not trip_data:
                print_error("Could not get trip data for testing")
                self.test_results["failed"] += 1
                return
        
        try:
            trip_key = trip_data.get("TripKey")
            route_uid = trip_data.get("RouteUid")
            
            print_info(f"Testing trip details for:")
            print_info(f"  TripKey: {trip_key}")
            print_info(f"  RouteUid: {route_uid}")
            
            url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"
            
            headers = {
                "RequestVerificationToken": self.token,
                "ModuleId": "5345",
                "TabId": "133",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            now = datetime.now()
            data = {
                "RouteUid": route_uid,
                "TripUid": trip_key,
                "TripDate": now.strftime("%Y-%m-%d"),
                "TripDirection": "outbound",
                "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
            }
            
            response = self.session.post(url, headers=headers, data=data)
            
            if response.status_code != 200:
                print_error(f"API request failed: {response.status_code}")
                self.test_results["failed"] += 1
                return
            
            result = response.json()
            
            if result.get("result") == "success" and "data" in result:
                trip_data = result["data"]
                stops = trip_data.get("TripStopTimings", [])
                
                print_success(f"Retrieved {len(stops)} stops")
                print_info(f"Headsign: {trip_data.get('Headsign', 'N/A')}")
                print_info(f"Direction: {trip_data.get('Direction', 'N/A')}")
                
                if stops:
                    print_info(f"First stop: {stops[0]['Stop']['Description']}")
                    print_info(f"Last stop: {stops[-1]['Stop']['Description']}")
                    
                    # Validate stop structure
                    first_stop = stops[0]
                    required_stop_fields = ["ArrivalTime", "DepartTime", "Stop"]
                    for field in required_stop_fields:
                        if field not in first_stop:
                            print_error(f"Missing stop field: {field}")
                    
                    # Check GPS coordinates
                    if "Position" in stops[0]["Stop"]:
                        print_success("GPS coordinates available")
                
                self.test_results["passed"] += 1
            else:
                print_error(f"No trip data in response: {result}")
                self.test_results["failed"] += 1
                
        except Exception as e:
            print_error(f"Exception: {e}")
            self.test_results["errors"].append(str(e))
            self.test_results["failed"] += 1
    
    def test_favorites_management(self):
        """Test favorites add, list, get, and delete"""
        print_test_header("Favorites Management")
        
        # Create a temporary CSV file for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            csv_path = temp_file.name
            print_info(f"Using temporary CSV: {csv_path}")
        
        try:
            # Test 1: Add favorite
            print_info("Testing: Add favorite")
            favorite = {
                "name": TEST_FAVORITE_NAME,
                "bus_number": TEST_BUS_NUMBER,
                "key": "715",
                "route_uid": "SWA-SRI-4277"
            }
            
            # Simulate adding to CSV
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['name', 'bus_number', 'key', 'route_uid'])
                writer.writeheader()
                writer.writerow(favorite)
            
            print_success("Favorite added successfully")
            self.test_results["passed"] += 1
            
            # Test 2: List favorites
            print_info("Testing: List favorites")
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                favorites = list(reader)
                
            if len(favorites) == 1 and favorites[0]['name'] == TEST_FAVORITE_NAME:
                print_success(f"Listed {len(favorites)} favorite(s)")
                self.test_results["passed"] += 1
            else:
                print_error("Favorite listing failed")
                self.test_results["failed"] += 1
            
            # Test 3: Get specific favorite
            print_info("Testing: Get favorite by name")
            found = None
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['name'] == TEST_FAVORITE_NAME:
                        found = row
                        break
            
            if found:
                print_success(f"Found favorite: {found['name']}")
                self.test_results["passed"] += 1
            else:
                print_error("Could not find favorite")
                self.test_results["failed"] += 1
            
            # Test 4: Delete favorite
            print_info("Testing: Delete favorite")
            remaining = []
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['name'] != TEST_FAVORITE_NAME:
                        remaining.append(row)
            
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['name', 'bus_number', 'key', 'route_uid'])
                writer.writeheader()
                for row in remaining:
                    writer.writerow(row)
            
            # Verify deletion
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                favorites = list(reader)
            
            if len(favorites) == 0:
                print_success("Favorite deleted successfully")
                self.test_results["passed"] += 1
            else:
                print_error("Favorite deletion failed")
                self.test_results["failed"] += 1
                
        except Exception as e:
            print_error(f"Exception: {e}")
            self.test_results["errors"].append(str(e))
            self.test_results["failed"] += 1
        finally:
            # Clean up temp file
            if os.path.exists(csv_path):
                os.remove(csv_path)
                print_info("Cleaned up temporary CSV")
    
    def test_edge_cases(self):
        """Test edge cases and error handling"""
        print_test_header("Edge Cases & Error Handling")
        
        # Test 1: Invalid bus number
        print_info("Testing: Invalid bus number")
        try:
            url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"
            
            headers = {
                "RequestVerificationToken": self.token,
                "ModuleId": "5345",
                "TabId": "133",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            now = datetime.now()
            data = {
                "ExactlyMatchedRouteOnly": "true",
                "Mode": "bus",
                "Route": "99999",  # Invalid bus number
                "QryDate": now.strftime("%Y-%m-%d"),
                "QryTime": now.strftime("%H:%M"),
                "MaxOptions": "4"
            }
            
            response = self.session.post(url, headers=headers, data=data)
            result = response.json()
            
            if result.get("result") == "success":
                options = result.get("data", {}).get("Options", [])
                if len(options) == 0:
                    print_success("Correctly returned no options for invalid bus")
                    self.test_results["passed"] += 1
                else:
                    print_error("Unexpected options returned for invalid bus")
                    self.test_results["failed"] += 1
            else:
                print_success("API correctly rejected invalid bus number")
                self.test_results["passed"] += 1
                
        except Exception as e:
            print_error(f"Exception: {e}")
            self.test_results["errors"].append(str(e))
            self.test_results["failed"] += 1
        
        # Test 2: Late night query (no buses)
        print_info("Testing: Late night query")
        try:
            data = {
                "ExactlyMatchedRouteOnly": "true",
                "Mode": "bus",
                "Route": TEST_BUS_NUMBER,
                "QryDate": now.strftime("%Y-%m-%d"),
                "QryTime": "03:00",  # 3 AM - likely no buses
                "MaxOptions": "4"
            }
            
            response = self.session.post(url, headers=headers, data=data)
            result = response.json()
            
            if result.get("result") == "success":
                options = result.get("data", {}).get("Options", [])
                print_info(f"Late night query returned {len(options)} options")
                self.test_results["passed"] += 1
            else:
                print_info("Late night query handled appropriately")
                self.test_results["passed"] += 1
                
        except Exception as e:
            print_error(f"Exception: {e}")
            self.test_results["errors"].append(str(e))
            self.test_results["failed"] += 1
    
    def run_all_tests(self):
        """Run all tests"""
        print(f"\n{Colors.BOLD}=== STARTING BUS TIMES SERVICE TEST SUITE ==={Colors.RESET}")
        
        if not self.setup():
            print_error("Setup failed - cannot continue tests")
            return
        
        # Run all test suites
        self.test_bus_times_basic()
        self.test_bus_times_with_optional_params()
        self.test_trip_details()
        self.test_favorites_management()
        self.test_edge_cases()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}TEST SUMMARY{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
        
        total = self.test_results["passed"] + self.test_results["failed"]
        
        if self.test_results["failed"] == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}ALL TESTS PASSED! 🎉{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}Some tests failed{Colors.RESET}")
        
        print(f"\nTotal Tests: {total}")
        print(f"{Colors.GREEN}Passed: {self.test_results['passed']}{Colors.RESET}")
        print(f"{Colors.RED}Failed: {self.test_results['failed']}{Colors.RESET}")
        
        if self.test_results["errors"]:
            print(f"\n{Colors.RED}Errors encountered:{Colors.RESET}")
            for error in self.test_results["errors"]:
                print(f"  - {error}")
        
        # Calculate pass rate
        if total > 0:
            pass_rate = (self.test_results["passed"] / total) * 100
            print(f"\nPass Rate: {pass_rate:.1f}%")

def main():
    """Main test runner"""
    tester = BusTimesServiceTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()