import argparse
import ast
import json
from pathlib import Path


def box_center(label):
    points = label.get("points") or []
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return {
        "center_x": (min(xs) + max(xs)) / 2.0,
        "center_y": (min(ys) + max(ys)) / 2.0,
    }


def sort_labels(labels, order="horizontal"):
    sortable = []
    for idx, label in enumerate(labels):
        try:
            center = box_center(label)
        except Exception:
            center = {"center_x": 0.0, "center_y": 0.0}
        sortable.append({"idx": idx, **center})
    if len(sortable) < 2:
        return labels

    left_center = min(item["center_x"] for item in sortable)
    right_center = max(item["center_x"] for item in sortable)
    if order in ("vertical-lr", "vertical-rl"):
        left_to_right = order == "vertical-lr"
        if right_center - left_center < 80:
            ordered = sorted(sortable, key=lambda item: (item["center_y"], item["center_x"]))
            return [labels[item["idx"]] for item in ordered]
        sorted_by_x = sorted(
            sortable,
            key=lambda item: item["center_x"],
            reverse=not left_to_right,
        )
        avg_width = 0.0
        widths = []
        for label in labels:
            try:
                points = label.get("points") or []
                xs = [float(point[0]) for point in points]
                widths.append(max(xs) - min(xs))
            except Exception:
                pass
        if widths:
            avg_width = sum(widths) / len(widths)
        threshold = avg_width * 0.5 if avg_width > 0 else 10.0
        columns = []
        current_col = [sorted_by_x[0]]
        last_x = sorted_by_x[0]["center_x"]
        for item in sorted_by_x[1:]:
            if abs(item["center_x"] - last_x) <= threshold:
                current_col.append(item)
            else:
                columns.append(current_col)
                current_col = [item]
            last_x = item["center_x"]
        if current_col:
            columns.append(current_col)
        ordered = []
        for col in columns:
            col.sort(key=lambda item: (item["center_y"], item["center_x"]))
            ordered.extend(col)
        return [labels[item["idx"]] for item in ordered]

    if right_center - left_center < 80:
        ordered = sorted(sortable, key=lambda item: (item["center_y"], item["center_x"]))
        return [labels[item["idx"]] for item in ordered]

    for _ in range(8):
        left = []
        right = []
        for item in sortable:
            if abs(item["center_x"] - left_center) <= abs(item["center_x"] - right_center):
                left.append(item)
            else:
                right.append(item)
        if not left or not right:
            break
        new_left = sum(item["center_x"] for item in left) / len(left)
        new_right = sum(item["center_x"] for item in right) / len(right)
        if new_left == left_center and new_right == right_center:
            break
        left_center, right_center = new_left, new_right

    split = (left_center + right_center) / 2.0
    left = [item for item in sortable if item["center_x"] < split]
    right = [item for item in sortable if item["center_x"] >= split]
    if not left or not right:
        ordered = sorted(sortable, key=lambda item: (item["center_y"], item["center_x"]))
    else:
        left.sort(key=lambda item: (item["center_y"], item["center_x"]))
        right.sort(key=lambda item: (item["center_y"], item["center_x"]))
        ordered = left + right
    return [labels[item["idx"]] for item in ordered]


def parse_label_text(text):
    try:
        return json.loads(text)
    except Exception:
        return ast.literal_eval(text)


def resort_file(path, order="horizontal"):
    if not path.exists():
        return 0
    original = path.read_text(encoding="utf-8")
    changed = 0
    lines = []
    for line in original.splitlines():
        if not line.strip() or "\t" not in line:
            lines.append(line)
            continue
        image_name, label_text = line.split("\t", 1)
        labels = parse_label_text(label_text)
        sorted_labels = sort_labels(labels, order=order)
        if sorted_labels != labels:
            changed += 1
        lines.append(
            image_name
            + "\t"
            + json.dumps(sorted_labels, ensure_ascii=False)
        )
    if changed:
        backup = path.with_suffix(path.suffix + ".bak")
        backup.write_text(original, encoding="utf-8")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


def main():
    parser = argparse.ArgumentParser(
        description="Resort PPOCRLabel Label.txt/Cache.cach by reading order."
    )
    parser.add_argument("directory", help="Image directory containing Label.txt or Cache.cach")
    parser.add_argument(
        "--order",
        choices=["horizontal", "vertical-lr", "vertical-rl"],
        default="horizontal",
        help="horizontal: top-to-bottom rows; vertical-lr: vertical text columns left-to-right; vertical-rl: vertical text columns right-to-left.",
    )
    args = parser.parse_args()

    root = Path(args.directory)
    total = 0
    for name in ("Label.txt", "Cache.cach"):
        path = root / name
        changed = resort_file(path, order=args.order)
        total += changed
        if path.exists():
            print(f"{path}: resorted {changed} page(s)")
    print(f"Done. Resort entries: {total}")


if __name__ == "__main__":
    main()
