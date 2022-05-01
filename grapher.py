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

VIDEO_FRAMES_DIR = "video-frames"
try:
    os.makedirs(VIDEO_FRAMES_DIR)
except OSError:
    pass

DATA_FETCH_PERIOD_MS = 250  # milliseconds
HILL_CLIMB_MULT = 10  # resolution multiplier for hill climbing

MODE_HILL_CLIMB = "hill-climb"
MODE_HILL_CLIMB_RET = "hill-climb-ret"
MODE_HILL_CLIMB_EXT = "hill-climb-ext"
MODE_SCAN_RESET = "scan-reset"
MODE_SCAN_EXT = "scan-ext"
MODE_SCAN_RET = "scan-ret"

BG_COLOR = pygame.Color("#000000")
TEXT_COLOR = pygame.Color("#FFFFFF")
TEXT_OUTLINE_COLOR = pygame.Color("#FF0000")

#LEVELS = [pygame.Color("#150050"), pygame.Color("#3F0071"), pygame.Color("#610094")]  # Dark Purple
#HILL_CLIMB_LEVELS = [pygame.Color("#385000"), pygame.Color("#327100"), pygame.Color("#339400")]
LEVELS = [pygame.Color("#150050"), pygame.Color("#610094")]  # Dark Purple
HILL_CLIMB_LEVELS = [pygame.Color("#385000"), pygame.Color("#339400")]
HILL_CLIMB_DOT = pygame.Color("#57F50A")

if not pygame.font:
    print("Warning, fonts disabled")

GRAPHER_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
if not os.path.isfile(GRAPHER_FONT):
    GRAPHER_FONT = None


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


        if data["age"] > 5:
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

def draw_dot(x, y, bar_width, dot_color, surf, radius):
    # put the bar on the chart
    bar = pygame.Rect(x, surf.get_height() - y, bar_width, surf.get_height())
    center = (x, surf.get_height() - y)
    pygame.draw.circle(surf, dot_color, center, radius)



DATA_Q = queue.Queue(maxsize=5)

class DataFetcherThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.start()

        self.liveData = RandomTestData()
        self.liveData = LiveData(local=True)
        self.liveData = LiveData()

    def run(self):
        while (True):
            start_s = time.time()
            print("{} <--- Current queue size".format(DATA_Q.qsize()))

            try:
                trackerData = self.liveData.next()
            except Exception as e:
                trackerData = {}
                trackerData["exception"] = e

            DATA_Q.put(trackerData)

            run_duration_s = time.time() - start_s
            sleep_for_s = DATA_FETCH_PERIOD_MS / 1000 - run_duration_s

            print("Sleeping for {} seconds".format(sleep_for_s))
            if sleep_for_s > 0:
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
    print("Screen size: {}".format(screen.get_size()))
    pygame.mouse.set_visible(False)

    # Create The Backgound
    background = pygame.Surface(screen.get_size())
    background = background.convert()
    background.fill(BG_COLOR)

    # Surface 1 (bars only)
    bar_chart = pygame.Surface(screen.get_size())
    bar_chart = bar_chart.convert()

    # Surface 2 (bars and dots)
    bar_dot_chart = pygame.Surface(screen.get_size())
    bar_dot_chart = bar_dot_chart.convert()

    # Surface 3 (pring errors)
    errSurf = pygame.Surface(screen.get_size())
    errSurf = errSurf.convert()
    errSurf.fill(BG_COLOR)

    # Zoom Surface
    ZOOM_W = 300
    ZOOM_H = 200
    zoomSurf = pygame.Surface((ZOOM_W, ZOOM_H))
    zoomSurf = errSurf.convert()
    zoomSurf.fill(BG_COLOR)


    # Display The Background
    screen.blit(background, (0, 0))

    clock = pygame.time.Clock()

    levelChart = LevelChart(background.get_height())

    frame_num = 0
    video_start = time.time()

    first_scan_ext = True

    # Main Loop
    done = False
    mode = None

    while not done:
        # clock.tick(80)
        # pygame.time.wait(200)

        level = 0
        pos = 0
        watts = None

        trackerData = DATA_Q.get()
        print(trackerData)

        if "exception" in trackerData:
            # erase previous error
            errSurf.fill(BG_COLOR)

            # draw a footer indicating an error
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
                font = pygame.font.Font(GRAPHER_FONT, 32)
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
            pos = trackerData["pos"] / HILL_CLIMB_MULT
            efficiency_pct = trackerData.get("efficiency_pct")

            value = (watts / LiveData.MAX_VALUE) * background.get_height() * len(LEVELS)
            offset, level = levelChart.get_offset(value)
            bar_height = offset
            bar_color = LEVELS[level]
            bar_width = 10

            if mode == MODE_SCAN_EXT:
                if first_scan_ext:
                    print("Erasing dot chart!")
                    bar_dot_chart.blit(bar_chart, (0, 0))
                    first_scan_ext = False

                # draw bars on both surfaces
                for i in [bar_chart, bar_dot_chart]:
                    draw_bar(pos, level, bar_height, bar_width, bar_color, i)
            else:
                first_scan_ext = True

            if mode == MODE_SCAN_RET:
                for i in [bar_chart, bar_dot_chart]:
                    draw_bar(pos, level, bar_height, bar_width, bar_color, i)

            if mode.startswith(MODE_HILL_CLIMB):
                w = background.get_width()
                h = background.get_height()

                dot_x = pos * bar_width
                dot_y = bar_height

                # historical dot on the main chart
                dot_color = HILL_CLIMB_LEVELS[level]
                draw_dot(dot_x, dot_y, bar_width, dot_color, surf=bar_dot_chart, radius=5)

                # main chart
                background.blit(bar_dot_chart, (0, 0))

                # latest dot
                dot_color = HILL_CLIMB_DOT
                draw_dot(dot_x, dot_y, bar_width, dot_color, surf=background, radius=10)

                # zoom chart
                zoom_level = 3
                size = (w * zoom_level, h * zoom_level)
                x_offset = (0.5 * ZOOM_W) - (dot_x * zoom_level)
                y_offset = (0.5 * ZOOM_H) - ((h - dot_y) * zoom_level)
                offset = (x_offset, y_offset)
                zoomed_surf_tmp = pygame.transform.scale(bar_dot_chart, size)
                zoomSurf.fill(BG_COLOR)
                zoomSurf.blit(zoomed_surf_tmp, offset, (0, 0, 0 - x_offset + ZOOM_W, 0 - y_offset + ZOOM_H))
                pygame.draw.rect(zoomSurf, pygame.Color("red"), (0, 0, 1, ZOOM_H))
                pygame.draw.rect(zoomSurf, pygame.Color("red"), (0, 0, ZOOM_W, 1))
                pygame.draw.rect(zoomSurf, pygame.Color("red"), (ZOOM_W - 1, 0, ZOOM_W, ZOOM_H))
                pygame.draw.rect(zoomSurf, pygame.Color("red"), (0, ZOOM_H -1, ZOOM_W, ZOOM_H))
                background.blit(zoomSurf, (0, 0), (0, 0, ZOOM_W, ZOOM_H))

                # since we're zoomed and panned, just draw this in the middle
                draw_dot(ZOOM_W / 2, h - (ZOOM_H / 2), bar_width, HILL_CLIMB_DOT, surf=background, radius=15)
            else:
                background.blit(bar_dot_chart, (0, 0))

            # put text on the background
            if pygame.font and watts:
                # Watts
                font = pygame.font.Font(GRAPHER_FONT, 250)
                text = "{}W".format(int(watts))
                wattsTextSurf = font.render(text, True, TEXT_COLOR)
                text_width = wattsTextSurf.get_width()
                wattsTextPos = wattsTextSurf.get_rect(
                    centery=background.get_height() / 2,
                    x=(background.get_width() - text_width)
                )
                background.blit(wattsTextSurf, wattsTextPos)

                # Efficiency
                if efficiency_pct is not None:
                    font = pygame.font.Font(GRAPHER_FONT, 48)
                    text = "gain %d%%" % (efficiency_pct - 100)
                    effTextSurf = font.render(text, True, TEXT_COLOR)
                    text_width = effTextSurf.get_width()
                    textpos = effTextSurf.get_rect(
                        centery=(background.get_height() / 2) + (wattsTextPos.h / 2),
                        x=(background.get_width() - text_width)
                    )
                    background.blit(effTextSurf, textpos)


            # Draw Everything
            screen.blit(background, (0, 0))

        pygame.display.flip()

        if frame_num % 100 == 0:
            video_duration = time.time() - video_start
            fps = frame_num / video_duration
            print("FPS: %.3f (video duration: %.3fs)" % (fps, video_duration))

        # Save every frame
        frame_num += 1
        filename = VIDEO_FRAMES_DIR + ("/%06d.png" % (frame_num))
        pygame.image.save(background, filename)


    pygame.quit()


# Game Over


# this calls the 'main' function when this script is executed
if __name__ == "__main__":
    main()
