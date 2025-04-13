import os
import sys
import time
import requests
from datetime import datetime
import argparse

# Function to check and install colorama if missing
def install_colorama():
    try:
        import colorama
        from colorama import Fore, Back, Style, init
    except ImportError:
        print("[ERROR] 'colorama' not found. Installing...")  # No color here yet
        os.system(f"{sys.executable} -m pip install colorama")
        print("[INFO] 'colorama' installed successfully. Restarting the script...")
        time.sleep(2)  # Give some time for installation
        os.execv(sys.executable, ['python'] + sys.argv)  # Restart the script with the same arguments
    else:
        # Initialize Colorama if installed
        init(autoreset=True)
        return Fore, Back, Style  # Return these to use later

# Ensure colorama is available
Fore, Back, Style = install_colorama()  # Now we safely have colorama available

# Base configuration
base_url = "http://192.168.0.1"
index_url = f"{base_url}/index.html"
json_url = f"{base_url}/data.json"
img_base_url = f"{base_url}/img/"
check_interval = 1  # seconds between availability checks

# Argument parsing
parser = argparse.ArgumentParser(description="Download files from the specified server.")
parser.add_argument('--verbose', action='store_true', help="Enable verbose logging.")
parser.add_argument('--output_folder', type=str, default="downloads", help="Folder to save the downloaded files.")
args = parser.parse_args()

verbose = args.verbose
output_folder = args.output_folder

def log_section(title):
    print("\n" + "=" * 80)
    print(f"{Fore.YELLOW}[ {datetime.now().strftime('%H:%M:%S')} | STEP ] {title.upper()}")
    print("=" * 80 + "\n")

def verbose_log(message, color=Fore.WHITE):
    if verbose:
        print(f"{color}[{datetime.now().strftime('%H:%M:%S')} | INFO ] {message}")

def verbose_error(message, color=Fore.RED):
    print(f"{color}[{datetime.now().strftime('%H:%M:%S')} | ERROR] {message}")

def wait_for_ip():
    log_section("Initialization: Waiting for Target Device at 192.168.0.1")

    verbose_log("Starting low-bandwidth monitoring loop.", Fore.CYAN)
    verbose_log(f"Sending HEAD requests to: {index_url}", Fore.CYAN)
    verbose_log(f"Checking every {check_interval} second(s) for a live connection.", Fore.CYAN)

    is_online = False
    last_log_time = 0
    log_interval = 10  # Log every 10 seconds max while waiting

    while True:
        try:
            start_time = time.time()
            response = requests.head(index_url, timeout=0.5)
            response_time = time.time() - start_time

            if response.status_code == 200:
                if not is_online:
                    log_section("Device Online: index.html is Now Reachable")
                    verbose_log("HEAD request succeeded. Dumping connection details:", Fore.GREEN)
                    verbose_log(f"HTTP Status Code: {response.status_code}", Fore.GREEN)
                    verbose_log(f"Response Time: {response_time:.3f} seconds", Fore.GREEN)
                    verbose_log("Response Headers:", Fore.GREEN)

                    # Output all headers
                    for key, value in response.headers.items():
                        verbose_log(f"  {key}: {value}", Fore.YELLOW)

                    # Connection details (IP and port)
                    try:
                        connection_info = response.raw._connection.sock.getpeername()
                        verbose_log(f"Connected to IP: {connection_info[0]}", Fore.GREEN)
                        verbose_log(f"Remote Port: {connection_info[1]}", Fore.GREEN)
                    except Exception as e:
                        verbose_log(f"Could not retrieve connection details: {e}", Fore.RED)

                is_online = True
                break
            else:
                if time.time() - last_log_time > log_interval:
                    verbose_log(f"Received unexpected HTTP status: {response.status_code}, still waiting...", Fore.YELLOW)
                    last_log_time = time.time()
        except requests.exceptions.RequestException as e:
            if time.time() - last_log_time > log_interval:
                verbose_log(f"Still waiting for device to come online... (Error: {e})", Fore.RED)
                last_log_time = time.time()

        time.sleep(check_interval)

def fetch_data_json():
    log_section("Fetching Metadata File: data.json")

    try:
        verbose_log(f"Sending GET request to: {json_url}", Fore.CYAN)
        response = requests.get(json_url)
        status = response.status_code
        verbose_log(f"HTTP response received with status code: {status}", Fore.CYAN)
        response.raise_for_status()

        json_data = response.json()
        file_list = json_data.get("FileNames", [])
        verbose_log(f"Total filenames retrieved from JSON: {len(file_list)}", Fore.CYAN)

        if not file_list:
            raise ValueError("The 'FileNames' list is empty or missing in data.json.")

        verbose_log("Displaying all filenames found in data.json:", Fore.GREEN)
        for idx, fname in enumerate(file_list, 1):
            verbose_log(f"  {idx:02d}. {fname}", Fore.YELLOW)

        ext = os.path.splitext(file_list[0])[1].lower()
        verbose_log(f"Auto-detected file extension from first filename: {ext}", Fore.GREEN)

        filtered_files = [f for f in file_list if f.lower().endswith(ext)]
        verbose_log(f"Total files matching extension '{ext}': {len(filtered_files)}", Fore.GREEN)
        return filtered_files, ext

    except Exception as e:
        verbose_error(f"Failed to retrieve or parse data.json: {e}", Fore.RED)
        sys.exit(1)

def download_files(file_list, extension):
    log_section(f"Beginning Download Process for {extension} Files")

    # Ensure the output folder exists
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for index, filename in enumerate(file_list, 1):
        file_url = f"{img_base_url}{filename}"
        verbose_log(f"[{index}/{len(file_list)}] Preparing to download: {file_url}", Fore.CYAN)

        try:
            verbose_log(f"Initiating stream download from: {file_url}", Fore.CYAN)
            response = requests.get(file_url, stream=True)
            status = response.status_code
            verbose_log(f"Received HTTP status code: {status}", Fore.CYAN)
            response.raise_for_status()

            content_length = response.headers.get('content-length')
            total_size = int(content_length) if content_length else None
            if total_size:
                verbose_log(f"Content-Length header found: {total_size} bytes ({total_size / (1024 * 1024):.2f} MB)", Fore.GREEN)
            else:
                verbose_log("Content-Length header missing. Progress tracking may be unavailable.", Fore.YELLOW)

            verbose_log(f"Saving file as: {filename}", Fore.CYAN)
            downloaded_bytes = 0
            chunk_size = 8192

            output_file_path = os.path.join(output_folder, filename)
            with open(output_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        if total_size:
                            percent = (downloaded_bytes / total_size) * 100
                            sys.stdout.write(
                                f"\r[DOWNLOAD] {downloaded_bytes / (1024 * 1024):.2f} MB of {total_size / (1024 * 1024):.2f} MB ({percent:.2f}%)"
                            )
                        else:
                            sys.stdout.write(
                                f"\r[DOWNLOAD] {downloaded_bytes / (1024):.2f} KB downloaded..."
                            )
                        sys.stdout.flush()

            print("\n[✓] Download complete:", filename)

        except Exception as e:
            verbose_error(f"Failed to download file '{filename}': {e}", Fore.RED)

    log_section("Download Process Complete")
    verbose_log("All matching files have been downloaded successfully.", Fore.GREEN)
    print("\n[✓] Script has completed all operations. You're good to go!")

# ---------------------------
# Main script flow
# ---------------------------

if __name__ == "__main__":
    verbose_log("Script started.", Fore.GREEN)
    wait_for_ip()
    file_list, file_ext = fetch_data_json()
    download_files(file_list, file_ext)