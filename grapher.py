#!/usr/bin/env python

# Import Modules
import os
import random
import pygame
import requests

# for video exporter
import time

# for data fetching
import threading
import queue

HOME = os.path.expanduser("~")


VIDEO_FRAMES_DIR = HOME + "/video-frames"
try:
    os.makedirs(VIDEO_FRAMES_DIR)
except OSError:
    pass

TARGET_FRAME_RATE = 2  # frames per second

SCAN_NUM_MOVES = 100 # drives screen width

DATA_FETCH_MIN_PERIOD_MS = 100  # milliseconds, reduce CPU use on tracker brains

MODE_HILL_CLIMB = "hill-climb"
MODE_HILL_CLIMB_RET = "hill-climb-ret"
MODE_HILL_CLIMB_EXT = "hill-climb-ext"
MODE_SCAN_EXT = "scan-ext"
MODE_SCAN_RET = "scan-ret"

ZOOM_LEVEL = 5
BG_COLOR = pygame.Color("#000000")
TEXT_COLOR = pygame.Color("#FFFFFF")
TEXT_OUTLINE_COLOR = pygame.Color("#FF0000")

LEVELS_RAW = ["#9055A2", "#D499B9", "#E8C1C5"]
LEVELS = [pygame.Color(x) for x in LEVELS_RAW]
HILL_CLIMB_LEVELS_RAW = ["#6F7C12", "#8CFF98", "#AAD922"]
HILL_CLIMB_LEVELS_RAW = ["#0000BB"]  # blue
HILL_CLIMB_LEVELS = [pygame.Color(x) for x in HILL_CLIMB_LEVELS_RAW]

NUM_LEVELS = 1
LEVELS = LEVELS[0:NUM_LEVELS]
HILL_CLIMB_LEVELS = HILL_CLIMB_LEVELS[0:NUM_LEVELS]

LATEST_DOT_COLOR = pygame.Color("#57F50A")  # green
PROBE_DOT_COLOR = pygame.Color("#222222")  # gray

POS_DEG_TO_GRAPH_RATIO = 1.5


if not pygame.font:
    print("Warning, fonts disabled")

GRAPHER_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
if not os.path.isfile(GRAPHER_FONT):
    GRAPHER_FONT = None


def _color_add(base, offset):
    if 0 < (base + offset) < 256:
        return base + offset
    else:
        return base

class ColorShift(object):
    def __init__(self, start_color):
        if not start_color.startswith("#"):
            raise Exception("Expecting hex color for {}".format(start_color))

        start_color = start_color[1:]  # chop off the "#"
        triplet = start_color[0:2], start_color[2:4], start_color[4:6]

        self.base_color = [int(t, 16) for t in triplet]
        self.offset_current = 0
        self.offset_min = 0
        self.offset_max = 70

    def next(self):
        if self.offset_current < self.offset_max:
            self.offset_current += 0.3
        else:
            self.offset_current = 0

        hex_triplet = [hex(_color_add(c, int(self.offset_current)))[2:].zfill(2) for c in self.base_color]
        return pygame.Color("#{}{}{}".format(*hex_triplet))

    def reset(self):
        self.offset_current = 0


# TODO: after removing LEVELS, add this only to historical dots (in main and zoom)
# Rational: makes it possible to tell which historical dots are newer
histDotColorShift = ColorShift(str(HILL_CLIMB_LEVELS_RAW[0]))

class RandomTestData(object):
    MAX_VALUE = 100

    def __init__(self):
        self.direction = "up"
        self.prev_value = 0

    def next(self):
        delta = random.random() - 0.5
        if self.direction == "up":
            if delta > 0:
                delta *= 2
        else:
            if delta < 0:
                delta *= 2

        new_value = self.prev_value + delta * 5
        if new_value < 0:
            new_value = 0
            self.direction = "up"

        if new_value > RandomTestData.MAX_VALUE:
            new_value = RandomTestData.MAX_VALUE
            self.direction = "down"

        self.prev_value = new_value
        return {'value': new_value, 'age': time.time()}


class LiveDataError(Exception):
    pass

class LiveDataStartingUp(Exception):
    pass

class LiveDataStale(Exception):
    pass

class LiveDataNoConnection(Exception):
    pass

ERROR_COLOR_MAP = {
   LiveDataError: pygame.Color("red"),
   LiveDataStartingUp: pygame.Color("blue"),
   LiveDataStale: pygame.Color("green"),
   LiveDataNoConnection: pygame.Color("gray")
}


class LiveData(object):
    MAX_VALUE = 100
    URL = "http://10.55.0.11:9732"
    PARAMS = {}
    TIMEOUT_S = 2.0

    def __init__(self, local=False):
        if local:
            self.url = "http://127.0.0.1:9732"
        else:
            self.url = LiveData.URL

    def next(self):
        try:
            resp = requests.get(url=self.url, params=LiveData.PARAMS, timeout=LiveData.TIMEOUT_S)
        except Exception as msg:
            raise LiveDataNoConnection(msg)

        try:
            data = resp.json()
            if "starting" in data:
                raise LiveDataStartingUp("Staring up...")

            if "value" not in data or "age" not in data:
                raise LiveDataError("Wrong json: {}".format(data))
        except LiveDataStartingUp:
            raise
        except Exception as msg:
            raise LiveDataError("Unknown exception: {}".format(msg))


        if data["age"] > 300:
            raise LiveDataStale("Age is {} seconds".format(data["age"]))

        return data


class LevelChart(object):
    def __init__(self, screen_height):
        self.screen_height = screen_height

    def get_offset(self, value):
        offset = value
        level_count = 0 
        while(offset > self.screen_height):
            offset -= self.screen_height
            level_count += 1

        if level_count > len(LEVELS) - 1:
            level_count = len(LEVELS) - 1

        return offset, level_count


def draw_bar(pos, level, bar_height, bar_width, bar_color, chart):
    # put the bar on the chart
    bar = pygame.Rect(pos * bar_width, chart.get_height() - bar_height, bar_width, chart.get_height())
    pygame.draw.rect(chart, bar_color, bar)

    # put the anti-bar on the chart
    if level == 0:
        antibar_color = BG_COLOR
    else:
        antibar_color = LEVELS[level - 1]

    antibar_height = chart.get_height() - bar_height
    antibar = pygame.Rect(pos * bar_width, 0, bar_width, antibar_height)
    pygame.draw.rect(chart, antibar_color, antibar)

    ## shift
    #chart.blit(chart, (-bar_width, 0))

def draw_dot(x, y, dot_color, surf, radius):
    pygame.draw.circle(surf, dot_color, (x, y), radius)



DATA_Q = queue.Queue(maxsize=5)

class DataFetcherThread(threading.Thread):
    def __init__(self):
        self.start_s = time.time()
        self.liveData = RandomTestData()
        self.liveData = LiveData(local=True)
        self.liveData = LiveData()

        threading.Thread.__init__(self)
        self.daemon = True
        self.start()

    def run(self):
        while (True):
            try:
                trackerData = self.liveData.next()
            except AttributeError as e:
                raise
            except Exception as e:
                trackerData = {}
                trackerData["exception"] = e

            DATA_Q.put(trackerData)

            run_duration_s = time.time() - self.start_s
            #print("---> Fetch duration {:.3f} / queue size {}".format(run_duration_s, DATA_Q.qsize()))
            sleep_for_s = DATA_FETCH_MIN_PERIOD_MS / 1000 - run_duration_s
            self.start_s = time.time()
            if sleep_for_s > 0:
                print("Sleeping for {}s to reduce CPU usage on tracker-brains".format(sleep_for_s))
                time.sleep(sleep_for_s)


# Run in the background
DataFetcherThread()


def main():
    """this function is called when the program starts.
    it initializes everything it needs, then runs in
    a loop until the function returns."""
    # Initialize Everything
    # pygame.init() ## commented out - don't initialize sound to avoid ALSA warnings "underrun occurred"

    pygame.display.init()
    pygame.font.init()
    screen = pygame.display.set_mode()

    print("[[[[[[[[[ Screen size: {} ]]]]]]]]]".format(screen.get_size()))
    # my device screen size is 800 x 480
    SCREEN_W = 798
    SCREEN_H = 478
    pygame.mouse.set_visible(False)

    # Create The Background
    background = pygame.Surface((SCREEN_W, SCREEN_H)).convert()

    # Foreground Surface
    FG_W = SCREEN_W - 3
    FG_H = SCREEN_H * 0.6 - 1  # foreground takes bottom % of vertical space
    fgSurf = pygame.Surface((FG_W, FG_H)).convert()
    fgSurf.fill(BG_COLOR)

    # Surface 1 (bars only)
    bar_chart = pygame.Surface(fgSurf.get_size()).convert()

    # Surface 2 (bars and probes)
    bar_probe_chart = pygame.Surface(fgSurf.get_size()).convert()

    # Surface 4 (print errors)
    errSurf = pygame.Surface((SCREEN_W, SCREEN_H)).convert()
    errSurf.fill(BG_COLOR)

    # Zoom Surface
    ZOOM_H = SCREEN_H - FG_H - 10  # take the rest of vertical space
    ZOOM_W = SCREEN_W * 0.6
    zoomSurf = pygame.Surface((ZOOM_W, ZOOM_H)).convert()
    zoomSurf.fill(BG_COLOR)

    # Display The Background
    screen.blit(background, (0, 0))

    levelChart = LevelChart(FG_H)

    frame_num = 0
    video_mon_start = None
    video_start = time.time()

    first_scan_ext = True
    first_hill_climb = True

    frame_start = time.time()

    decision_dots = []

    # Main Loop
    done = False
    mode = None

    clock = pygame.time.Clock()

    while not done:
        clock.tick(10)  # max is 10 frames per second

        level = 0
        pos = 0
        watts = None

        trackerData = DATA_Q.get()
        #print(trackerData)
        render_start = time.time()

        if "exception" in trackerData:
            # erase previous error
            errSurf.fill(BG_COLOR)

            # draw a footer indicating an error
            #print(trackerData["exception"])
            error_color = ERROR_COLOR_MAP[type(trackerData["exception"])]
            footer_height = 50
            footer = pygame.Rect(0, errSurf.get_height() - footer_height, errSurf.get_width(), footer_height)
            pygame.draw.rect(errSurf, error_color, footer)

            # put name of the exception in the rectangle
            if pygame.font:
                font = pygame.font.Font(GRAPHER_FONT, 32)
                text = type(trackerData["exception"]).__name__
                textSurf = font.render(text, True, BG_COLOR)
                text_width = textSurf.get_width()
                textpos = textSurf.get_rect(
                    centery=(errSurf.get_height() - footer_height / 2),
                    centerx=(errSurf.get_width() / 2),
                )
                errSurf.blit(textSurf, textpos)

            # put text of the exception on the errSurf
            if pygame.font:
                font = pygame.font.Font(GRAPHER_FONT, 16)
                text = str(trackerData["exception"])
                textLines = []
                terminal_width = 40
                while text != "":
                    textLines.append(text[0:terminal_width])
                    text = text[terminal_width:]

                y_offset = 0
                margin = 10
                linespacing = 10
                for line in textLines: 
                    textSurf = font.render(line, True, TEXT_COLOR)
                    text_width = textSurf.get_width()
                    textpos = textSurf.get_rect(
                        y=y_offset,
                        x=(errSurf.get_width() - text_width - margin)
                    )
                    y_offset += (linespacing + textpos.h)
                    errSurf.blit(textSurf, textpos)

            # Draw Everything
            screen.blit(errSurf, (0, 0))
        else:
            watts = trackerData["value"]
            mode = trackerData["mode"]
            pos = trackerData["pos"] * POS_DEG_TO_GRAPH_RATIO
            is_probe = trackerData["is_probe"]
            is_decision = trackerData["is_decision"]
            efficiency_pct = trackerData.get("efficiency_pct")
            wobble_data = trackerData.get("wobble_data")

            value = (watts / LiveData.MAX_VALUE) * FG_H * len(LEVELS)
            offset, level = levelChart.get_offset(value)
            bar_height = offset
            bar_color = LEVELS[level]
            dot_color = HILL_CLIMB_LEVELS[level]
            bar_width = FG_W / SCAN_NUM_MOVES

            # clear background
            background.fill(BG_COLOR)

            if mode == MODE_SCAN_EXT:
                if first_scan_ext:
                    print("Erasing dot chart!")
                    decision_dots = []
                    bar_probe_chart.blit(bar_chart, (0, 0))
                    first_scan_ext = False

                # draw bars on both surfaces
                for i in [bar_chart, bar_probe_chart]:
                    draw_bar(pos, level, bar_height, bar_width, bar_color, i)
            else:
                first_scan_ext = True

            if mode.startswith(MODE_HILL_CLIMB):
                # zoom chart
                zoom_surf_size = (FG_W * ZOOM_LEVEL, FG_H * ZOOM_LEVEL)
                if first_hill_climb:
                    zoomedUncroppedSurf = pygame.transform.scale(bar_chart, zoom_surf_size)

                dot_x = pos * bar_width
                dot_y = FG_H - bar_height

                # historical dot (main)
                if is_probe:
                    draw_dot(dot_x, dot_y, PROBE_DOT_COLOR, surf=bar_probe_chart, radius=15)
                else:
                    dot = (dot_x, dot_y)
                    decision_dots.append(dot)

                # main chart
                fgSurf.blit(bar_probe_chart, (0, 0))

                # draw decision path (main)
                histDotColorShift.reset()
                for dot in decision_dots:
                    color = histDotColorShift.next()
                    draw_dot(*dot, color, surf=fgSurf, radius=10)

                # latest dot
                draw_dot(dot_x, dot_y, LATEST_DOT_COLOR, surf=fgSurf, radius=10)
                border_w = ZOOM_W / ZOOM_LEVEL
                border_h = ZOOM_H / ZOOM_LEVEL
                border_left = dot_x - border_w / 2
                border_top = dot_y - border_h / 2
                border_right = dot_x - border_w / 2
                border_bottom = dot_y + border_h / 2
                pygame.draw.rect(fgSurf, pygame.Color("red"), (border_left, border_top, 1, border_h))
                pygame.draw.rect(fgSurf, pygame.Color("red"), (border_left, border_top, border_w, 1))
                pygame.draw.rect(fgSurf, pygame.Color("red"), (border_left + border_w, border_top, 1, border_h))
                pygame.draw.rect(fgSurf, pygame.Color("red"), (border_left, border_top + border_h, border_w, 1))

                x_offset = (0.5 * ZOOM_W) - (dot_x * ZOOM_LEVEL)
                y_offset = (0.5 * ZOOM_H) - (dot_y * ZOOM_LEVEL)
                offset = (x_offset, y_offset)

                # historical dot (zoom)
                if is_probe:
                    draw_dot(dot_x * ZOOM_LEVEL, dot_y * ZOOM_LEVEL, PROBE_DOT_COLOR,
                        surf=zoomedUncroppedSurf, radius=15)

                # draw decision path (main)
                histDotColorShift.reset()
                for dot in decision_dots:
                    color = histDotColorShift.next()
                    draw_dot(dot[0] * ZOOM_LEVEL, dot[1] * ZOOM_LEVEL, color, surf=zoomedUncroppedSurf, radius=10)

                zoomSurf.fill(BG_COLOR)
                zoomSurf.blit(zoomedUncroppedSurf, offset, (0, 0, 0 - x_offset + ZOOM_W, 0 - y_offset + ZOOM_H))

                # zoom chart: border
                pygame.draw.rect(zoomSurf, pygame.Color("red"), (0, 0, 1, ZOOM_H))
                pygame.draw.rect(zoomSurf, pygame.Color("red"), (0, 0, ZOOM_W, 1))
                pygame.draw.rect(zoomSurf, pygame.Color("red"), (ZOOM_W - 1, 0, ZOOM_W, ZOOM_H))
                pygame.draw.rect(zoomSurf, pygame.Color("red"), (0, ZOOM_H -1, ZOOM_W, ZOOM_H))

                background.blit(zoomSurf, (0, 0), (0, 0, ZOOM_W, ZOOM_H))

                # since we're zoomed and panned, just draw this in the middle
                draw_dot(ZOOM_W / 2, ZOOM_H / 2, LATEST_DOT_COLOR, surf=background, radius=10)

                first_hill_climb = False
            else:
                fgSurf.blit(bar_probe_chart, (0, 0))
                first_hill_climb = True

            # foreground chart: border
            pygame.draw.rect(fgSurf, pygame.Color("white"), (0, 0, 1, FG_H))
            pygame.draw.rect(fgSurf, pygame.Color("white"), (0, 0, FG_W, 1))
            pygame.draw.rect(fgSurf, pygame.Color("white"), (FG_W - 1, 0, FG_W, FG_H))
            pygame.draw.rect(fgSurf, pygame.Color("white"), (0, FG_H -1, FG_W, FG_H))

            background.blit(fgSurf, (0, SCREEN_H - FG_H))

            # put text on the background
            if pygame.font and watts is not None:
                # Watts
                font = pygame.font.Font(GRAPHER_FONT, 60)
                text = "{}W".format(int(watts))
                wattsTextSurf = font.render(text, True, TEXT_COLOR)
                text_width = wattsTextSurf.get_width()
                wattsTextPos = wattsTextSurf.get_rect(
                    y=5,
                    x=(SCREEN_W - text_width)
                )
                background.blit(wattsTextSurf, wattsTextPos)

                # Efficiency
                if efficiency_pct is not None:
                    font = pygame.font.Font(GRAPHER_FONT, 25)
                    text = "gain %d%%" % (efficiency_pct - 100)
                    effTextSurf = font.render(text, True, TEXT_COLOR)
                    text_width = effTextSurf.get_width()
                    textpos = effTextSurf.get_rect(
                        y=(5 + wattsTextPos.h),
                        x=(SCREEN_W - text_width)
                    )
                    background.blit(effTextSurf, textpos)

                # Wobble
                if wobble_data is not None:
                    font = pygame.font.Font(GRAPHER_FONT, 25)
                    text = "wobble {}s {}s {}%".format(*[int(x) for x in wobble_data])
                    effTextSurf = font.render(text, True, TEXT_COLOR)
                    text_width = effTextSurf.get_width()
                    textpos = effTextSurf.get_rect(
                        y=(5 + wattsTextPos.h + 25),
                        x=(SCREEN_W - text_width)
                    )
                    background.blit(effTextSurf, textpos)


            # Draw Everything
            screen.blit(background, (0, 0))

        pygame.display.flip()

        MON_WINDOW_NUM_FRAMES = 100
                
        if frame_num % MON_WINDOW_NUM_FRAMES == 0:
            if video_mon_start is not None:
                mon_duration = time.time() - video_mon_start
                fps = MON_WINDOW_NUM_FRAMES / mon_duration
                print("\n\n===\nFPS: %.3f (video duration: %.3fs)" % (fps, mon_duration))

                # correcting if we undershot. undershooting happens more often then overshooting.
                expected_duration = MON_WINDOW_NUM_FRAMES / TARGET_FRAME_RATE
                if mon_duration < expected_duration:
                    correction_delay = expected_duration - mon_duration
                    print("Correcting by {:.3f} seconds".format(correction_delay))
                    pygame.time.delay(int(correction_delay * 1000))

                print("===\n")

            video_mon_start = time.time()

        # Save every frame
        frame_num += 1
        filename = VIDEO_FRAMES_DIR + ("/%06d.png" % (frame_num))
        pygame.image.save(screen, filename)


        #print("Render time: {:.3f}s\n\n".format(time.time() - render_start))

        ## Wait the rest of allotted time
        frame_duration = time.time() - frame_start
        delay = (1 / TARGET_FRAME_RATE) - frame_duration
        if delay > 0:
            pygame.time.delay(int(delay * 1000))  # target 2 frames per second
        frame_start = time.time()


    pygame.quit()


# Game Over


# this calls the 'main' function when this script is executed
if __name__ == "__main__":
    main()
