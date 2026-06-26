"""
ORB recognition robustness test — synthetic perturbations of a single reference image.

Uses the EXACT same algorithm and parameters as the production code:
  - src/nav_assistant/localization/place_recognizer.py (ORB_create(nfeatures=500),
    BFMatcher NORM_HAMMING, Lowe's ratio test at 0.75, confidence = good/250)
  - src/nav_assistant/mapping/recorder.py (_ORB_N_FEATURES = 500)

Methodology: extract a reference descriptor set from one real photo (simulating
a trained location), then apply controlled synthetic transformations (rotation,
Gaussian blur, brightness change) to simulate what a user would see from a
different angle, while moving, or under different lighting -- the same kinds
of change that occur if a user deviates from the exact trained viewpoint.
Match each perturbed version against the reference and record the same
good_matches/confidence the real PlaceRecognizer would compute.

This is a controlled desktop validation, NOT a field test on the deployed
Raspberry Pi hardware (which is no longer available). It uses one sample
image, so results characterize ORB's general sensitivity to these specific
perturbation types, not a statistically representative accuracy figure for
the full trained system.
"""

import cv2
import numpy as np
import json

ORB_N_FEATURES = 500
LOWE_RATIO = 0.75
MIN_GOOD_MATCHES = 15
CONFIDENCE_THRESHOLD = 0.6

orb = cv2.ORB_create(nfeatures=ORB_N_FEATURES)
matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)


def extract(gray):
    _, des = orb.detectAndCompute(gray, None)
    return des


def match_against_reference(query_des, ref_des):
    if query_des is None or len(query_des) < 2:
        return 0, 0.0
    matches = matcher.knnMatch(query_des, ref_des, k=2)
    good = [m for m, n in matches if m.distance < LOWE_RATIO * n.distance]
    confidence = min(1.0, len(good) / 250)
    return len(good), confidence


def rotate(img, angle):
    h, w = img.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)


def blur(img, ksize):
    if ksize == 0:
        return img
    return cv2.GaussianBlur(img, (ksize, ksize), 0)


def brightness(img, delta):
    return cv2.convertScaleAbs(img, alpha=1.0, beta=delta)


def main():
    # Run from anywhere; path is relative to this script's location.
    from pathlib import Path
    image_path = Path(__file__).parent.parent.parent / "photos" / "hardwarePhoto.jpg"
    ref_img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    ref_des = extract(ref_img)
    print(f"Reference descriptors: {len(ref_des)}\n")

    results = {"rotation": [], "blur": [], "brightness": []}

    print("=== Rotation (simulating viewpoint change / user deviating angle) ===")
    for angle in [0, 5, 10, 15, 20, 30, 45, 60, 90]:
        test_img = rotate(ref_img, angle)
        des = extract(test_img)
        good, conf = match_against_reference(des, ref_des)
        recognized = good >= MIN_GOOD_MATCHES and conf >= CONFIDENCE_THRESHOLD
        print(f"  angle={angle:3d} deg | good_matches={good:4d} | confidence={conf:.3f} | recognized={recognized}")
        results["rotation"].append({"angle": angle, "good_matches": good, "confidence": conf, "recognized": recognized})

    print("\n=== Gaussian blur (simulating motion blur while walking) ===")
    for k in [0, 3, 5, 9, 15, 21]:
        test_img = blur(ref_img, k)
        des = extract(test_img)
        good, conf = match_against_reference(des, ref_des)
        recognized = good >= MIN_GOOD_MATCHES and conf >= CONFIDENCE_THRESHOLD
        print(f"  kernel={k:3d}     | good_matches={good:4d} | confidence={conf:.3f} | recognized={recognized}")
        results["blur"].append({"kernel": k, "good_matches": good, "confidence": conf, "recognized": recognized})

    print("\n=== Brightness change (simulating different lighting conditions) ===")
    for delta in [0, -60, -40, -20, 20, 40, 60]:
        test_img = brightness(ref_img, delta)
        des = extract(test_img)
        good, conf = match_against_reference(des, ref_des)
        recognized = good >= MIN_GOOD_MATCHES and conf >= CONFIDENCE_THRESHOLD
        print(f"  delta={delta:4d}    | good_matches={good:4d} | confidence={conf:.3f} | recognized={recognized}")
        results["brightness"].append({"delta": delta, "good_matches": good, "confidence": conf, "recognized": recognized})

    out_path = Path(__file__).parent / "orb_robustness_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved raw results to {out_path}")


if __name__ == "__main__":
    main()
