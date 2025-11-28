import json
import os
import logging
from bs4 import BeautifulSoup
import asyncio
from urllib.parse import urlparse
import modules.config as config

logger = logging.getLogger("OgameBot")

class EmpireManager:
    def __init__(self, data_file=os.path.join("data", "empire_data.json")):
        self.data_file = os.path.abspath(data_file)
        self.data = self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load empire data: {e}")
        return {"planets": []}

    def save_data(self):
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save empire data: {e}")

    async def fetch_data(self, context):
        """
        Fetches empire data using the existing browser context.
        """
        try:
            base_url = self._get_base_url()
            logger.info("🕷 Starting Empire Crawl...")
            page = await context.new_page()
            
            # 1. Navigate to Home page to get Planet IDs
            logger.info(f"Navigate to Home page for Planet IDs... (base: {base_url})")
            home_url = f"file:///{config.LOCAL_FILE_PATH}" if config.USE_LOCAL_FILE else f"{base_url}/home"
            await page.goto(home_url, timeout=60000)
            home_content = await page.content()
            
            # Parse IDs from Home page
            coords_to_id = self.extract_planet_ids(home_content)
            logger.info(f"Extracted {len(coords_to_id)} planet IDs from Home page")

            # 2. Navigate to empire view
            empire_url = f"{base_url}/empire"
            logger.info(f"Navigate to Empire page for data... ({empire_url})")
            response = await page.goto(empire_url, timeout=60000)
            
            if not response or not response.ok:
                status = response.status if response else "n/a"
                status_text = response.status_text if response else "no response"
                logger.error(f"Failed to fetch empire page: {status} {status_text}")
                logger.error(f"Final URL reached: {page.url}")
                await page.close()
                return False

            content = await page.content()
            await page.close()

            # Parse the HTML with the extracted IDs
            self.parse_empire_html(content, coords_to_id)
            self.save_data()
            logger.info("✅ Empire Crawl Completed!")
            return True

        except Exception as e:
            logger.error(f"Error during empire crawl: {e}")
            return False

    def extract_planet_ids(self, html_content):
        """
        Extracts planet and moon IDs from the Home page HTML.
        Returns a dict: {coords: {"planet_id": str, "moon_id": str or None}}
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            coords_to_ids = {}
            
            planet_items = soup.select('.planet-item')
            for wrapper in planet_items:
                planet_link = wrapper.select_one('.planet-select')
                if not planet_link:
                    continue

                href = planet_link.get('href', '')
                if 'planet=' not in href:
                    continue

                planet_id = href.split('planet=')[1].split('&')[0]

                coords_span = planet_link.select_one('.planet-coords')
                coords = None
                if coords_span:
                    c_text = coords_span.get_text(strip=True)
                    import re
                    match = re.search(r'\[\d+:\d+:\d+\]', c_text)
                    if match:
                        coords = match.group(0)
                if not coords:
                    logger.warning(f"No coords parsed for planet link {href}")
                    continue

                moon_link = wrapper.select_one('.moon-select')
                moon_id = None
                if moon_link:
                    moon_href = moon_link.get('href', '')
                    if 'planet=' in moon_href:
                        moon_id = moon_href.split('planet=')[1].split('&')[0]

                coords_to_ids[coords] = {"planet_id": planet_id, "moon_id": moon_id}
                logger.info(f"Mapped {coords} -> planet {planet_id} moon {moon_id}")
            
            logger.info(f"Final Coords Map: {coords_to_ids}")
            return coords_to_ids
        except Exception as e:
            logger.error(f"Error extracting planet IDs: {e}")
            return {}

    def parse_empire_html(self, html_content, coords_to_id=None):
        """
        Parses the Empire page HTML and extracts planet info.
        """
        if coords_to_id is None:
            coords_to_id = {}
            
        logger.info(f"Parsing Empire HTML with ID Map keys: {list(coords_to_id.keys())}")
            
        try:
            # Save debug file first
            with open(os.path.join("debug", "empire_debug.html"), "w", encoding="utf-8") as f:
                f.write(html_content)
            
            soup = BeautifulSoup(html_content, 'html.parser')
            planets = []
            
            # 1. Identify Planets from the top header section
            container = (
                soup.select_one('.planetViewContainer')
                or soup.select_one('.planet-view-container')
                or soup.select_one('#empire-container')
                or soup.select_one('.empire-container')
            )
            if not container:
                logger.error("Could not find empire container (.planetViewContainer / .planet-view-container / #empire-container)")
                return

            # The first child div contains the headers/planet info
            # It usually has style="float:left; width:100%;"
            header_row_div = container.find('div', recursive=False)
            if not header_row_div:
                logger.error("Could not find header row div")
                return

            # Get all columns in the header row
            header_cols = header_row_div.select('.col')
            logger.info(f"Found {len(header_cols)} columns in header row")
            
            planet_indices = []
            
            for i, col in enumerate(header_cols):
                # Check if this column represents a planet
                # Planets have coordinates. The "Sum" column has an empty coords span.
                coords_span = col.select_one('.planet-coords')
                if coords_span:
                    name_span = col.select_one('.planet-name')
                    name = name_span.get_text(strip=True) if name_span else "Unknown"
                    coords = coords_span.get_text(strip=True)
                    
                    # Skip if coords are empty (likely the Sum column)
                    if not coords:
                        logger.debug(f"Column {i} skipped (Empty coords). Likely Sum column.")
                        continue

                    # Extract fields if available
                    fields_span = col.select_one('.planet-fields')
                    fields = fields_span.get_text(strip=True) if fields_span else ""
                    
                    # Extract temperature
                    temp_span = col.select_one('.planet-temperature')
                    temp = temp_span.get_text(strip=True) if temp_span else ""

                    # Lookup IDs
                    mapping = coords_to_id.get(coords, {})
                    if isinstance(mapping, dict):
                        p_id = mapping.get("planet_id", "")
                        moon_id = mapping.get("moon_id")
                    else:
                        p_id = mapping
                        moon_id = None

                    if not p_id:
                        logger.warning(f"No ID found for coords '{coords}'. Available keys: {list(coords_to_id.keys())}")
                    else:
                        logger.info(f"Successfully matched {coords} to ID {p_id}")

                    logger.info(f"Found planet: {name} {coords} (ID: {p_id}) at col index {i}")
                    
                    planets.append({
                        "id": p_id,
                        "name": name,
                        "coords": coords,
                        "fields": fields,
                        "moon_name": f"{name} - Moon" if moon_id else "",
                        "moon_id": moon_id or "",
                        "temperature": temp,
                        "resources": {},
                        "production": {},
                        "facilities": {},
                        "ships": {},
                        "defense": {},
                        "research": {}
                    })
                    planet_indices.append(i)
                else:
                    # Debug log for non-planet columns (Header or Sum)
                    txt = col.get_text(strip=True)[:20]
                    logger.debug(f"Column {i} skipped (No coords). Text: {txt}")

            logger.info(f"Identified {len(planets)} planets")

            # 2. Extract Data from Property Rows
            prop_rows = container.select('.prop-row')
            
            for row in prop_rows:
                # Get the category title
                title_div = row.select_one('.prop-title')
                if not title_div:
                    continue
                
                category_title = title_div.get_text(strip=True)
                
                # Determine data key based on title and content
                data_key = None
                is_resource_buildings = False
                
                if "Resources" in category_title:
                    # Check if it's the Resource Buildings section (Mines) or actual Resources
                    # We look at the first label
                    first_label = row.select_one('.prop-sub-title span')
                    if first_label and "Mine" in first_label.get_text():
                        data_key = "facilities"
                        is_resource_buildings = True
                    else:
                        data_key = "resources"
                elif "Production" in category_title:
                    data_key = "production"
                elif "Storage" in category_title:
                    data_key = "resources" # Add storage to resources
                elif "Facilities" in category_title:
                    data_key = "facilities"
                elif "Ships" in category_title:
                    data_key = "ships"
                elif "Defenses" in category_title:
                    data_key = "defense"
                elif "Researches" in category_title:
                    data_key = "research"
                
                if not data_key:
                    continue

                # Get Labels
                header_col = row.select_one('.col.header')
                if not header_col:
                    continue
                    
                labels = [el.get_text(strip=True) for el in header_col.select('.prop-sub-title span')]
                
                # Get Data Columns in this row
                # Note: These should correspond 1:1 with header_cols
                data_cols = row.select('.col')
                
                # Iterate over our identified planets
                for p_idx, planet in enumerate(planets):
                    col_idx = planet_indices[p_idx]
                    
                    if col_idx < len(data_cols):
                        col = data_cols[col_idx]
                        # Values are in .cell-value
                        # There is usually a .cell-empty-value first which aligns with nothing (or the title?)
                        # The labels align with .cell-value elements
                        values = [el.get_text(strip=True) for el in col.select('.cell-value')]
                        
                        # Map labels to values
                        for l_idx, label in enumerate(labels):
                            if l_idx < len(values):
                                # Clean key
                                key = label.lower().replace(' ', '_').replace('(', '').replace(')', '')
                                # Clean value (remove dots)
                                val = values[l_idx].replace('.', '')
                                
                                # Special handling for Storage to avoid overwriting or confusion
                                if "storage" in category_title.lower() and data_key == "resources":
                                    key = f"{key}_capacity"

                                # Store
                                planet[data_key][key] = val

            self.data["planets"] = planets
            logger.info(f"Parsed {len(planets)} planets successfully")
            
        except Exception as e:
            logger.error(f"Error parsing empire HTML: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def get_data(self):
        return self.data

    def _get_base_url(self):
        """Derive the base URL from LIVE_URL to support different servers."""
        try:
            parsed = urlparse(config.LIVE_URL)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            pass
        return "https://mars.ogamex.net"
