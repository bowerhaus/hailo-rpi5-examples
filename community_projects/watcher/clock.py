import os
import json
import logging
from PIL import Image  # New import for image generation
import cv2  # Import OpenCV for drawing functions
from datetime import datetime, time

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

class Clock:
    def __init__(self, output_dir=config.get('OUTPUT_DIRECTORY', 'output')):
        self.output_dir = output_dir

    def build_data(self):
        records = []
        last_date = None
        first_record_of_day = True
        temp_storage = []

        # Iterate through date subdirectories
        for subdir in os.listdir(self.output_dir):
            subdir_path = os.path.join(self.output_dir, subdir)
            if os.path.isdir(subdir_path):
                # Load all JSON metadata files into temp_storage
                for filename in os.listdir(subdir_path):
                    if filename.endswith(".json"):
                        file_path = os.path.join(subdir_path, filename)
                        try:
                            with open(file_path, "r") as f:
                                data = json.load(f)
                            temp_storage.append((file_path, data))
                        except Exception as e:
                            print(f"Error reading {file_path}: {e}")

        # Sort temp_storage by timestamp
        temp_storage.sort(key=lambda x: x[1]['timestamp'])

        # Process each file from the sorted temp_storage
        for file_path, data in temp_storage:
            # Check if reviewed is true and label is HELEN_OUT or HELEN_BACK (case insensitive)
            label = data.get("label", "")
            if label:
                label = label.upper()
            if data.get("reviewed") and label in ("HELEN_OUT", "HELEN_BACK"):
                current_date = data['timestamp'][:8]  # Extract date from timestamp
                if current_date != last_date:
                    # New day
                    last_date = current_date
                    first_record_of_day = True

                if first_record_of_day:
                    if label != "HELEN_OUT":
                        logging.warning(f"First record of day {current_date} is not HELEN_OUT. Ignoring: {file_path}")
                        continue  # Ignore this record
                    first_record_of_day = False

                # Check for identical adjacent labels
                if records and records[-1]['label'] == data['label']:
                    logging.warning(f"Identical adjacent label found. Ignoring: {file_path}")
                    continue  # Ignore this record

                records.append(data)
        
        return records

    def build_clock(self):
        """
        Returns an array of records containing time periods and their counts.
        Each record now represents a 5-minute period in a 24-hour day with format:
        { 'time': datetime.time object, 'count': N }
        Total buckets = 288 (24×12).
        """
        # Initialize array of 288 time period records (5 min per bucket)
        clock_records = []
        for bucket in range(288):
            hour = bucket // 12
            minute = (bucket % 12) * 5
            clock_records.append({
                'time': time(hour=hour, minute=minute),
                'count': 0
            })

        records = self.build_data()
        if len(records) < 2:
            return clock_records

        # Process adjacent pairs of records (update conversion to 5-minute buckets)
        for i in range(0, len(records) - 1, 2):
            start_ts = records[i]['timestamp']
            end_ts = records[i + 1]['timestamp']

            # Convert timestamps to bucket indices (each bucket is 5 minutes)
            start_hour = int(start_ts[9:11])
            start_minute = int(start_ts[11:13])
            start_bucket = (start_hour * 12) + (start_minute // 5)

            end_hour = int(end_ts[9:11])
            end_minute = int(end_ts[11:13])
            end_bucket = (end_hour * 12) + (end_minute // 5)

            # Increment counts between start and end (inclusive)
            for bucket in range(start_bucket, end_bucket + 1):
                if 0 <= bucket < 288:
                    clock_records[bucket]['count'] += 1

        # Print only records with non-zero counts
        for record in clock_records:
            if record['count'] > 0:
                print(f"Time {record['time'].strftime('%H:%M')}: {record['count']}")
        return clock_records

    def draw_current_hour_hand(self, pil_image, size=1024, padding=50):
        """
        Draws the current hour hand overlay on the given PIL image.
        Returns a new PIL image with the overlay.
        """
        import numpy as np
        from datetime import datetime
        # Convert the PIL image to a NumPy array (RGBA)
        img_array = np.array(pil_image)

        center = size // 2
        radius = center - padding  # Add padding
        
        # Compute current time and hand angle (0 rad at 12:00)
        current_time = datetime.now().time()
        current_hour = current_time.hour % 12  
        current_minute = current_time.minute
        hour_fraction = (current_hour + current_minute / 60.0) / 12.0
        hand_angle = hour_fraction * 2 * np.pi
        
        # Compute the tip of the hand and base points for thickness
        hand_length = int(0.7 * radius)
        tip_x = int(center + hand_length * np.sin(hand_angle))
        tip_y = int(center - hand_length * np.cos(hand_angle))
        
        base_offset = 20  # Adjust for hand thickness
        base_left_x = int(center + base_offset * np.sin(hand_angle + np.pi/2))
        base_left_y = int(center - base_offset * np.cos(hand_angle + np.pi/2))
        base_right_x = int(center + base_offset * np.sin(hand_angle - np.pi/2))
        base_right_y = int(center - base_offset * np.cos(hand_angle - np.pi/2))
        
        import cv2
        triangle_pts = np.array([[base_left_x, base_left_y],
                                 [base_right_x, base_right_y],
                                 [tip_x, tip_y]], np.int32)
        triangle_pts = triangle_pts.reshape((-1, 1, 2))
        # Draw the hour hand as a white filled triangle.
        cv2.fillPoly(img_array, [triangle_pts], (255,255,255,255), lineType=cv2.LINE_AA)
        
        # Draw the central hub: a white circle with a dark grey outline.
        hub_radius = 30
        cv2.circle(img_array, (center, center), hub_radius, (255,255,255,255), -1)
        cv2.circle(img_array, (center, center), hub_radius, (64,64,64,255), 3, lineType=cv2.LINE_AA)
        
        return Image.fromarray(img_array, 'RGBA')
        
    def create_clock_image(self, size=1024, padding=50):
        """
        Creates a circular heatmap image for hours between 08:00 and 20:00.
        Uses a green-to-red gradient based on counts and overlays a current hour hand.
        """
        import numpy as np
        
        center = size // 2
        radius = center - padding  # Add padding
        
        # For 5-min buckets, 08:00 is bucket index 8*12 = 96, 20:00 is 20*12 = 240. Total = 144 buckets.
        clock_records = self.build_clock()
        day_records = clock_records[96:240]  # 144 buckets
        
        counts = np.array([record['count'] for record in day_records])
        max_count = counts.max() if counts.max() > 0 else 1
        normalized_counts = counts / max_count

        # Create base RGBA image
        img_array = np.zeros((size, size, 4), dtype=np.uint8)
        
        # Create coordinate grid and distances
        Y, X = np.ogrid[-center:center, -center:center]
        distances = np.sqrt(X*X + Y*Y)
        
        # Compute pixel angles using arctan2 and remap so that 12:00 is at the top.
        raw_angles = np.arctan2(X, -Y) % (2*np.pi)
        total_buckets = 144  # For 12 hours at 5-min resolution
        offset = 48  # 12:00 is 4 hours after 08:00 => 4*12 = 48 in day_records
        
        mask = distances <= radius
        for y in range(size):
            for x in range(size):
                if not mask[y, x]:
                    continue
                angle = raw_angles[y, x]
                base_index = int((angle / (2*np.pi)) * total_buckets)
                index = (base_index + offset) % total_buckets
                value = normalized_counts[index]
                # Densest green: #379900 -> (55,153,0)
                # Densest red:   #cc000e -> (204,0,14)
                red   = int((1 - value) * 55 + value * 204)
                green = int((1 - value) * 153 + value * 0)
                blue  = int((1 - value) * 0 + value * 14)
                img_array[y, x] = [red, green, blue, 255]
        
        # Apply an averaging filter to the entire image.
        blurred = cv2.blur(img_array, (15, 15))
        # Create a boolean mask to preserve the outer 10 pixels of the clock circle.
        inner_mask = (distances <= (radius - 10))[..., None]  # expand dims for RGBA
        combined = np.where(inner_mask, blurred, img_array)
        img_array = combined.astype(np.uint8)
        
        # Draw hour markers for each hour from 08:00 to 20:00 using 12-hour labels.
        for hour in range(8, 20):  # 8 to 19 inclusive; omit 20:00 label
            fraction = (hour - 12) / 12.0
            marker_angle = fraction * 2 * np.pi
            marker_x = int(center + 0.9 * radius * np.sin(marker_angle))
            marker_y = int(center - 0.9 * radius * np.cos(marker_angle))
            cv2.circle(img_array, (marker_x, marker_y), 5, (255,255,255,255), -1)
            display_hour = hour if hour <= 12 else hour - 12
            text_x = int(center + 0.75 * radius * np.sin(marker_angle))
            text_y = int(center - 0.75 * radius * np.cos(marker_angle))
            cv2.putText(img_array, str(display_hour), (text_x-15, text_y+15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255,255,255,255), 3, cv2.LINE_AA)

        # Draw an outline around the entire clock face in white with 15 pixel thickness.
        cv2.circle(img_array, (center, center), radius, (255,255,255,255), 15, lineType=cv2.LINE_AA)
        
        # Place the badge (existing code unchanged)
        const_badge_width = 300
        const_badge_height = 60
        hub_radius = 30
        target_center_y = center + (hub_radius + radius) / 3
        top_left_y = int(target_center_y - const_badge_height / 2)
        top_left = (center - const_badge_width // 2, top_left_y)
        bottom_right = (center + const_badge_width // 2, top_left_y + const_badge_height)
        cv2.rectangle(img_array, top_left, bottom_right, (204, 0, 14, 255), -1)
        text = "HELEN/O/CLOCK"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.9
        thickness = 2
        (text_width, text_height), _ = cv2.getTextSize(text, font, font_scale, thickness)
        text_x = center - text_width // 2
        text_y = top_left_y + (const_badge_height // 2) + (text_height // 2)
        cv2.putText(img_array, text, (text_x, text_y), font, font_scale, (255,255,255,255), thickness, cv2.LINE_AA)

        # After all drawing operations, convert the NumPy array to a PIL image.
        pil_img = Image.fromarray(img_array, 'RGBA')
        return pil_img

        
if __name__ == "__main__":
    clock = Clock()
    data = clock.build_clock()

    # Create clock heatmap image
    image = clock.create_clock_image()

    image = clock.draw_current_hour_hand(image)
    image.save("clock.png")
