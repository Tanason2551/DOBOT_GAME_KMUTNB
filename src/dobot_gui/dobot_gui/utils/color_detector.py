#!/usr/bin/env python3
"""
Color Detection & Perspective Rectification Engine for 3x3 Arena
Uses OpenCV HSV color segmentation, mask voting, and homography warping.
"""

import os
import json
from typing import Dict, List, Tuple, Optional, Any

try:
    import cv2
    import numpy as np
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False


# Supported color palette mapping to keys in Grid3x3Model.COLOR_PALETTE
# (H: 0..180, S: 0..255, V: 0..255 in OpenCV)
HSV_COLOR_RANGES = {
    "red": [
        ((0, 70, 50), (10, 255, 255)),
        ((165, 70, 50), (180, 255, 255))
    ],
    "orange": [
        ((11, 80, 70), (25, 255, 255))
    ],
    "yellow": [
        ((26, 70, 70), (35, 255, 255))
    ],
    "green": [
        ((36, 60, 50), (85, 255, 255))
    ],
    "cyan": [
        ((86, 60, 50), (100, 255, 255))
    ],
    "blue": [
        ((101, 70, 50), (130, 255, 255))
    ],
    "purple": [
        ((131, 60, 50), (164, 255, 255))
    ],
    "white": [
        ((0, 0, 160), (180, 50, 255))
    ]
}

# Grid mapping: (row, col) -> slot_id
GRID_SLOT_MAP = {
    (0, 0): 1,  # Slot 1 (บนซ้าย)
    (0, 1): 2,  # Slot 2 (บน)
    (0, 2): 3,  # Slot 3 (บนขวา)
    (1, 0): 4,  # Slot 4 (ซ้าย)
    (1, 1): 9,  # Center (จุดวาง)
    (1, 2): 5,  # Slot 5 (ขวา)
    (2, 0): 6,  # Slot 6 (ล่างซ้าย)
    (2, 1): 7,  # Slot 7 (ล่าง)
    (2, 2): 8   # Slot 8 (ล่างขวา)
}


class ColorDetector:
    """Performs perspective warping and HSV color classification for the 3x3 arena."""

    CONFIG_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "config",
        "camera_grid_corners.json"
    )

    @staticmethod
    def is_available() -> bool:
        return CV_AVAILABLE

    @classmethod
    def get_default_corners(cls, img_w: int = 640, img_h: int = 480, mode: str = "birds_eye") -> List[List[float]]:
        """Return default 4 corner points [TL, TR, BR, BL] for perspective adjustment."""
        if mode == "top_view":
            cx, cy = img_w / 2.0, img_h / 2.0
            half_size = min(img_w, img_h) * 0.35
            return [
                [cx - half_size, cy - half_size],  # TL
                [cx + half_size, cy - half_size],  # TR
                [cx + half_size, cy + half_size],  # BR
                [cx - half_size, cy + half_size]   # BL
            ]
        else:
            # Bird's-eye perspective trapezoid: narrower top, wider bottom
            cx, cy = img_w / 2.0, img_h / 2.0
            top_y = cy - 130.0
            bot_y = cy + 150.0
            top_half_w = 170.0
            bot_half_w = 230.0
            return [
                [cx - top_half_w, top_y],  # TL
                [cx + top_half_w, top_y],  # TR
                [cx + bot_half_w, bot_y],  # BR
                [cx - bot_half_w, bot_y]   # BL
            ]

    @classmethod
    def load_corners(cls, img_w: int = 640, img_h: int = 480) -> Tuple[List[List[float]], str]:
        """Load stored corner pins from JSON file, or fallback to defaults."""
        if os.path.exists(cls.CONFIG_FILE):
            try:
                with open(cls.CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                corners = data.get("corners")
                mode = data.get("mode", "birds_eye")
                if corners and len(corners) == 4:
                    return corners, mode
            except Exception:
                pass
        return cls.get_default_corners(img_w, img_h, "birds_eye"), "birds_eye"

    @classmethod
    def save_corners(cls, corners: List[List[float]], mode: str = "birds_eye"):
        """Save corner pins to JSON file for persistent calibration."""
        try:
            os.makedirs(os.path.dirname(cls.CONFIG_FILE), exist_ok=True)
            data = {
                "corners": corners,
                "mode": mode
            }
            with open(cls.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    @classmethod
    def warp_perspective(cls, frame: Any, corners: List[List[float]], out_size: int = 300) -> Optional[Any]:
        """
        Warp an input frame using 4 corner points to a top-down square image of size (out_size, out_size).
        corners: [Top-Left, Top-Right, Bottom-Right, Bottom-Left]
        """
        if not CV_AVAILABLE or frame is None or len(corners) != 4:
            return None

        src_pts = np.float32(corners)
        dst_pts = np.float32([
            [0, 0],
            [out_size - 1, 0],
            [out_size - 1, out_size - 1],
            [0, out_size - 1]
        ])

        try:
            matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
            warped = cv2.warpPerspective(frame, matrix, (out_size, out_size))
            return warped
        except Exception:
            return None

    @classmethod
    def classify_roi_color(cls, roi_bgr: Any) -> Tuple[str, float]:
        """
        Classify the dominant color in an ROI using HSV mask voting.
        Returns (color_key, confidence).
        """
        if not CV_AVAILABLE or roi_bgr is None or roi_bgr.size == 0:
            return "white", 0.0

        # Convert to HSV
        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        total_pixels = float(roi_bgr.shape[0] * roi_bgr.shape[1])
        if total_pixels == 0:
            return "white", 0.0

        scores: Dict[str, float] = {}

        for color_key, ranges in HSV_COLOR_RANGES.items():
            combined_mask = None
            for lower, upper in ranges:
                lower_np = np.array(lower, dtype=np.uint8)
                upper_np = np.array(upper, dtype=np.uint8)
                mask = cv2.inRange(hsv, lower_np, upper_np)
                if combined_mask is None:
                    combined_mask = mask
                else:
                    combined_mask = cv2.bitwise_or(combined_mask, mask)

            count = cv2.countNonZero(combined_mask)
            scores[color_key] = count / total_pixels

        # Identify highest scoring color
        # Sort by score descending
        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_color, best_score = sorted_scores[0]

        # Prioritize chromatic colors over white if chromatic score is substantial
        if best_color == "white" and len(sorted_scores) > 1:
            second_color, second_score = sorted_scores[1]
            if second_score >= 0.22:
                return second_color, second_score

        # Minimum confidence threshold
        if best_score < 0.18:
            return "white", best_score

        return best_color, best_score

    @classmethod
    def extract_slot_rois(cls, warped_arena: Any, out_size: int = 300) -> Dict[int, Any]:
        """
        Extract sampling ROIs for each of the 9 slots from a warped arena image (out_size x out_size).
        Uses the upper-center 50% area of each cell to capture the top face of 25mm cubes cleanly.
        """
        if warped_arena is None:
            return {}

        cell_size = out_size // 3
        slot_rois: Dict[int, Any] = {}

        # 50% ROI dimensions
        roi_w = int(cell_size * 0.50)
        roi_h = int(cell_size * 0.50)
        # Offset to center-upper
        offset_x = (cell_size - roi_w) // 2
        offset_y = int((cell_size - roi_h) * 0.40)

        for (row, col), slot_id in GRID_SLOT_MAP.items():
            cell_x = col * cell_size
            cell_y = row * cell_size

            x1 = cell_x + offset_x
            y1 = cell_y + offset_y
            x2 = x1 + roi_w
            y2 = y1 + roi_h

            # Crop
            roi = warped_arena[y1:y2, x1:x2]
            slot_rois[slot_id] = roi

        return slot_rois

    @classmethod
    def detect_grid_colors(cls, frame: Any, corners: List[List[float]]) -> Dict[int, Tuple[str, float]]:
        """
        Full pipeline: Warp arena from frame, extract slot ROIs, and classify color for each slot.
        Returns dict: {slot_id: (color_key, confidence)} for slots 1..8 (and center 9).
        """
        if frame is None:
            return {}

        warped = cls.warp_perspective(frame, corners, out_size=300)
        if warped is None:
            return {}

        rois = cls.extract_slot_rois(warped, out_size=300)
        results: Dict[int, Tuple[str, float]] = {}

        for slot_id, roi in rois.items():
            color_key, conf = cls.classify_roi_color(roi)
            results[slot_id] = (color_key, conf)

        return results
