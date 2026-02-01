import asyncio
import io
import math
import random
from dataclasses import dataclass
from typing import List, Tuple

import discord
from redbot.core import commands

from PIL import Image, ImageDraw, ImageFont


@dataclass
class WheelItem:
    label: str
    weight: int


def _parse_items(tokens: List[str]) -> List[WheelItem]:
    items: List[WheelItem] = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue

        #try weight:label format (only split on first ":")
        if ":" in token:
            left, right = token.split(":", 1)
            left = left.strip()
            right = right.strip()
            if left.isdigit() and right:
                w = int(left)
                if w <= 0:
                    w = 1
                items.append(WheelItem(label=right, weight=w))
                continue

        #otherwise default weight 1
        items.append(WheelItem(label=token, weight=1))

    #merge duplicates (optional but usually nice)
    merged = {}
    for it in items:
        key = it.label
        merged[key] = merged.get(key, 0) + it.weight
    return [WheelItem(k, v) for k, v in merged.items()]


def _smallest_divisor_gt1(n: int) -> int:
    """Smallest divisor >1; returns n if prime (or n<=1)."""
    if n <= 3:
        return n
    if n % 2 == 0:
        return 2
    r = int(math.isqrt(n))
    for i in range(3, r + 1, 2):
        if n % i == 0:
            return i
    return n


def _rand_pastel(rng: random.Random) -> Tuple[int, int, int]:
    #pastel-ish: keep channels high
    return (rng.randint(80, 230), rng.randint(80, 230), rng.randint(80, 230))


def _choose_text_color(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    #perceived luminance; pick black/white for contrast
    #read wiki for more info, very cool topic!!
    #r, g, b = rgb
    #lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    #return (0, 0, 0) if lum > 140 else (255, 255, 255)

    #ok in practice and testing just pure white seems easier on the eyes in most cases
    return (255, 255, 255)


def _ease_out_cubic(t: float) -> float:
    #t in [0,1]
    return 1 - (1 - t) ** 3

def _alpha_composite_safe(dst: Image.Image, src: Image.Image, x: int, y: int) -> None:
    """
    Alpha-composite src onto dst at (x,y), clipping to dst bounds.
    Works even when src is partially/fully out-of-bounds.
    """
    dx0, dy0 = x, y
    dx1, dy1 = x + src.width, y + src.height

    #intersection rect in dst coords
    ix0 = max(0, dx0)
    iy0 = max(0, dy0)
    ix1 = min(dst.width, dx1)
    iy1 = min(dst.height, dy1)

    if ix0 >= ix1 or iy0 >= iy1:
        return  #fully outside

    #corresponding rect in src coords
    sx0 = ix0 - dx0
    sy0 = iy0 - dy0
    sx1 = sx0 + (ix1 - ix0)
    sy1 = sy0 + (iy1 - iy0)

    dst_crop = dst.crop((ix0, iy0, ix1, iy1))
    src_crop = src.crop((sx0, sy0, sx1, sy1))
    dst_crop.alpha_composite(src_crop)
    dst.paste(dst_crop, (ix0, iy0))

def _rotate_with_anchor(img: Image.Image, angle_deg: float, anchor_xy: Tuple[float, float]) -> Tuple[Image.Image, Tuple[float, float]]:
    """
    Rotate img by angle_deg (CCW, like Pillow), with expand=True, and return:
      (rotated_img, new_anchor_xy)
    """
    width, height = img.size
    cx, cy = width / 2.0, height / 2.0
    ax, ay = anchor_xy

    ang = math.radians(angle_deg)
    cos_a = math.cos(ang)
    sin_a = math.sin(ang)

    #In image coordinates (y down), CCW rotation corresponds to:
    #[ cos  sin]
    #[-sin  cos]
    def rot_point(x: float, y: float) -> Tuple[float, float]:
        x0, y0 = x - cx, y - cy
        xr = x0 * cos_a + y0 * sin_a
        yr = -x0 * sin_a + y0 * cos_a
        return (xr + cx, yr + cy)

    corners = [rot_point(0, 0), rot_point(width, 0), rot_point(width, height), rot_point(0, height)]
    min_x = min(x for x, _ in corners)
    min_y = min(y for _, y in corners)

    rax, ray = rot_point(ax, ay)
    new_anchor = (rax - min_x, ray - min_y)

    rotated = img.rotate(angle_deg, resample=Image.BICUBIC, expand=True)
    return rotated, new_anchor

def _build_wheel_base(items: List[WheelItem], size: int, margin: int, rng: random.Random) -> Tuple[Image.Image, List[Tuple[str, float, float]]]:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = cy = size // 2
    radius = (size // 2) - margin
    bbox = (cx - radius, cy - radius, cx + radius, cy + radius)

    total = sum(item.weight for item in items) or 1
    n = len(items)

    #sanity check, if somehow called with no items, just gonna leave
    if n == 0:
        return img, []

    #colors, get the smallest divisor (4 -> 2, 9 -> 3, 7 -> 7 etc)
    k = _smallest_divisor_gt1(n)
    if k <= 1:
        k = n

    if k == n:
        colors = [_rand_pastel(rng) for _ in range(n)]
    else:
        palette = [_rand_pastel(rng) for _ in range(k)]
        colors = [palette[i % k] for i in range(n)]

    #Font, used this one for Zuko Counter before so it's on hand
    try:
        font = ImageFont.truetype("arialbd.ttf", size=max(14, size // 24))
    except Exception:
        font = ImageFont.load_default()

    seg_ranges: List[Tuple[str, float, float]] = []
    label_jobs: List[Tuple[float, float, str, float, Tuple[int, int, int]]] = []  #tx, ty, label, rot, seg_color

    start_raw = 0.0

    #first pass, draw segments + record label jobs
    #adjust for weights as well
    for idx, item in enumerate(items):
        span = (item.weight / total) * 360.0
        end_raw = start_raw + span
        color = colors[idx]

        #draw segment, normalized to [0, 360] and split if it wraps
        start = start_raw % 360.0
        end = end_raw % 360.0

        if span >= 360.0:
            #Degenerate case that should literally never happen, but maybe;
            #one option fills everything. idk might be funny some day
            draw.pieslice(bbox, start=0, end=360, fill=color, outline=(20, 20, 20, 255), width=2)
            seg_ranges.append((item.label, 0.0, 360.0))
        elif start < end:
            draw.pieslice(bbox, start=start, end=end, fill=color, outline=(20, 20, 20, 255), width=2)
            seg_ranges.append((item.label, start, end))
        else:
            #Wraps past 360, draw two wedges
            draw.pieslice(bbox, start=start, end=360.0, fill=color, outline=(20, 20, 20, 255), width=2)
            draw.pieslice(bbox, start=0.0, end=end, fill=color, outline=(20, 20, 20, 255), width=2)
            seg_ranges.append((item.label, start, 360.0))
            seg_ranges.append((item.label, 0.0, end))

        #label position uses mid of RAW span, then normalized for trig
        mid_draw = ((start_raw + end_raw) / 2.0) % 360.0

        #Flip winding for labels, somehow it was tripping me up?!
        mid_label = (-mid_draw) % 360.0
        theta = math.radians(mid_label)
        inner_r = radius * 0.60

        tx = cx + inner_r * math.cos(theta)
        ty = cy - inner_r * math.sin(theta)  #(y-down corrected because ugh PIL)

        #was originally rot = mid_label + 90 but I think I prefer this
        rot = mid_label        
        inner_r = radius * 0.60

        label = item.label
        if len(label) > 24:
            label = label[:23] + "…"

        label_jobs.append((tx, ty, label, rot, color))

        start_raw = end_raw

    #second pass, draw all labels on top
    for tx, ty, label, rot, color in label_jobs:
        text_color = _choose_text_color(color)

        bbox_txt = draw.textbbox((0, 0), label, font=font)
        tw = bbox_txt[2] - bbox_txt[0]
        th = bbox_txt[3] - bbox_txt[1]

        pad_x = 6
        pad_y = 4

        #was bumping into an issue where the bottom of the text was getting sliiiiiightly cut off
        #so this should resolve
        extra_bottom = 6

        text_img = Image.new("RGBA", (tw + pad_x * 2, th + pad_y * 2 + extra_bottom), (0, 0, 0, 0))
        tdraw = ImageDraw.Draw(text_img)
        tdraw.text((pad_x, pad_y), label, font=font, fill=text_color, stroke_width=2, stroke_fill=(0, 0, 0, 120))

        anchor = (pad_x, pad_y + th / 2.0)
        text_rot, new_anchor = _rotate_with_anchor(text_img, rot, anchor)

        px = int(tx - new_anchor[0])
        py = int(ty - new_anchor[1])

        _alpha_composite_safe(img, text_rot, px, py)

    #Hub last (covers label overlaps near center)
    hub_r = int(radius * 0.08)
    draw.ellipse((cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r), fill=(30, 30, 30, 255), outline=(255, 255, 255, 80), width=2)

    return img, seg_ranges



def _build_arrow_overlay(canvas_w: int, canvas_h: int, wheel_center: Tuple[int, int], wheel_radius: int) -> Image.Image:
    """
    Arrow on the right side pointing left toward the wheel.
    """
    overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    cx, cy = wheel_center

    #Arrow tip sits near wheel edge on the right hand side
    tip_x = cx + wheel_radius + 6
    tip_y = cy

    #Arrow sizes
    arrowwidth = max(24, wheel_radius // 6) 
    arrowheight = max(28, wheel_radius // 5)

    #Triangle pointing left
    p1 = (tip_x, tip_y) 
    p2 = (tip_x + arrowwidth, tip_y - arrowheight // 2)
    p3 = (tip_x + arrowwidth, tip_y + arrowheight // 2)

    d.polygon([p1, p2, p3], fill=(245, 245, 245, 255), outline=(20, 20, 20, 255))
    d.line([p2, p3], fill=(20, 20, 20, 255), width=3)

    #tiny weeny shaft hehehe
    shaft_len = arrowwidth // 2
    shaft_h = max(6, arrowheight // 8)
    startx1 = tip_x + arrowwidth
    starty1 = tip_y - shaft_h // 2
    startx2 = startx1 + shaft_len
    starty2 = tip_y + shaft_h // 2
    d.rounded_rectangle([startx1, starty1, startx2, starty2], radius=shaft_h // 2, fill=(245, 245, 245, 255), outline=(20, 20, 20, 255), width=2)

    return overlay

def _render_spin_gif(items: List[WheelItem], seed: int) -> Tuple[bytes, str]:
    """
    Returns (gif_bytes, chosen_label)
    """
    rng = random.Random(seed)

    #Canvas / wheel sizing
    wheel_size = 512
    margin = 18

    wheel_img, seg_ranges = _build_wheel_base(items, wheel_size, margin, rng)

    #Place wheel on a slightly wider canvas to allow arrow on right
    canvas_w = wheel_size + 150
    canvas_h = wheel_size
    canvas_bg = (0, 0, 0, 0)

    cx = wheel_size // 2
    cy = wheel_size // 2
    wheel_radius = (wheel_size // 2) - margin

    arrow = _build_arrow_overlay(canvas_w, canvas_h, (cx, cy), wheel_radius)

    #Choose winner by weighted random
    population = [item.label for item in items]
    weights = [item.weight for item in items]
    chosen = rng.choices(population, weights=weights, k=1)[0]

    #Find that segment's mid angle in wheel coordinates
    chosen_start, chosen_end = None, None
    for label, start, end in seg_ranges:
        if label == chosen:
            chosen_start, chosen_end = start, end
            break
    if chosen_start is None:
        chosen_start, chosen_end = seg_ranges[0][1], seg_ranges[0][2]

    chosen_mid_draw = (chosen_start + chosen_end) / 2.0

    #We want chosen_mid (after rotation) to end up at arrow angle 0.
    #Rotating the wheel image by +rot degrees (Pillow rotate) rotates CCW.
    #A point at angle θ moves to θ+rot.
    #Need chosen_mid + final_rot == 0 (mod 360) => final_rot == -chosen_mid
    chosen_mid_label = (-chosen_mid_draw) % 360.0

    #Add multiple full spins and a little random offset within the chosen segment
    #so it doesn't always stop dead-center.
    jitter = rng.uniform(-0.35, 0.35) * (chosen_end - chosen_start)  #within the segment :party:
    final_rot = (-chosen_mid_label - jitter) % 360.0

    full_spins = rng.randint(5, 8)
    total_rot = full_spins * 360.0 + final_rot

    #Build frames
    frames: List[Image.Image] = []

    fps = 30
    duration_s = rng.uniform(2.5, 3.6)
    frame_count = max(40, int(duration_s * fps))

    for i in range(frame_count):
        t = i / (frame_count - 1)
        eased = _ease_out_cubic(t)
        rot = total_rot * eased

        #Rotate wheel
        rotated = wheel_img.rotate(rot, resample=Image.BICUBIC, expand=False, center=(wheel_size // 2, wheel_size // 2))

        #Compose on canvas
        frame = Image.new("RGBA", (canvas_w, canvas_h), canvas_bg)

        #Slight drop shadow behind wheel, make it look pretty enough
        shadow = Image.new("RGBA", (wheel_size, wheel_size), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse((margin + 6, margin + 10, wheel_size - margin + 6, wheel_size - margin + 10), fill=(0, 0, 0, 90))
        frame.alpha_composite(shadow, (0, 0))

        frame.alpha_composite(rotated, (0, 0))
        frame.alpha_composite(arrow, (0, 0))

        frames.append(frame)

    #encode GIF
    out = io.BytesIO()

    #loop=0 => do not loop (most viewers respect this as "play once")
    #however Discord does not give a shit about this; kept it anyway in case anyone downloads the gifs
    #so, encode GIF and set the final frame to be 30 seconds long
    #Discord will still loop, but we "hold" on the final frame.
    #not ideal but w/e

    base_ms = int(1000 / fps)
    hold_ms = 30000 
    durations = [base_ms] * len(frames)
    durations[-1] = hold_ms

    out = io.BytesIO()
    frames[0].save(out, format="GIF", save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=2, optimize=False)
    return out.getvalue(), chosen

class Wheel(commands.Cog):
    """Spin-the-wheel chooser (PIL GIF)."""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="wheel")
    async def wheel(self, ctx: commands.Context, *options: str):
        """
        Usage:
          ;wheel pizza chipotle
          ;wheel 3:pizza chipotle
          ;wheel 2:pizza 5:chipotle 1:sushi
        """
        items = _parse_items(list(options))
        if len(items) < 2:
            return await ctx.send("Give me at least 2 options, e.g. `;wheel pizza chipotle`")

        #seed ties the gif + outcome together; 
        #add message id so it differs per call :elmochaos:
        seed = (ctx.message.id ^ ctx.author.id) & 0xFFFFFFFF

        async with ctx.typing():
            gif_bytes, chosen = await asyncio.to_thread(_render_spin_gif, items, seed)

        file = discord.File(io.BytesIO(gif_bytes), filename="wheel.gif")
        await ctx.send(file=file, content=f"**Result:** ||{chosen}||")
