# gCodePerSec script - Adjust feed rate to slow down the number of gCode commands per second to a maximum rate
# It runs with the PostProcessingPlugin which is released under the terms of the AGPLv3 or higher.

# This script is licensed under the GNU Affero v3 terms.

# Copyright (c) 2020 Sophist

# Authors of the gCodePerSec plugin / script:
# 1. Written by:  Sophist, sophist.uk@gmail.com
# 2. Modified by: ...

# History / Change log:
# v0.1.0:   Initial version for trial
# v0.1.1:   Added helper functions for settings

# Note 1: This initial version will look at individual instructions rather than assessing groups of instructions.
#         So e.g. a single short segment may be slowed down even though it is surrounded by longer segments and would not normally cause an issue.
#         This may be addressed in a future enhancement using a smoothing algorithm - research will be needed to understand how the firmware e.g. Marlin
#         reads gCode ahead.
#
# Note 2: Because this adjusts individual segments, it is possible that feed rates may change frequently and vary significantly from segment to segment.
#         It is not known whether this frequent fluctuation in feedrate will cause issues. (Initial experimentation shows that it does.)
#         This may be also be addressed with a future smoothing algorithm.
#
# Note 3: Cura only produces liner moves using G0 and G1 - arcs and splines are not produced by CUra, but can be created by other postprocesasor scripts e.g. Anvil.
#         This version of the plugin does NOT handle arcs and splines. Cura does not produce arcs or splines itself, and the purpose of
#         e.g. Anvil is to reduce multiple small linear segments by converting them to longer arcs and splines in order to prevent spluttering.
#         If you want to run both scripts, ensure that Anvil runs before this one.
#
# Note 4: Only G0 and G1 statements take print time and have a feed rate that can be adjusted_feedrate. This script assumes
#         that other statements are infrequent and there is enough capacity to process them without stuttering.
#         If this proves not to be the case in practice, then for now you should reduce the maximum gCode per Sec by a small amount to compensate,
#         and if / when we implement a smoothing algorithm (e.g. to avoid big changes in feedrate) then this will be taken into account.

#import re
from typing import Any, List
from math import sqrt, floor
from datetime import timedelta

from UM.Application import Application #To get the current printer's settings.
from UM.Logger import Logger

from ..Script import Script

class gCodePerSec(Script):
    """Adjusts the feed rate if necessary to slow down the number of gCode commands per second to a maximum rate.

    For each gCode command, the script evaluates how long it takes to print, and adjusts the feedrate if necessary
    so that it takes at least 1/Maximum rate seconds to execute, subject also to a slowest allowed print speed.
        """

    def __init__(self) -> None:
        super().__init__()
        Logger.log("d", "gCodePerSec: _init_ called.")

    def getSettingDataString(self) -> str:
        return ("""        {
            "name": "Gcode max lines per Second",
            "key": "gCodePerSec",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "enabled":
                {
                    "label": "Enable this script?",
                    "description": "Enable this script to adjust feed rate to limit the number of gCode instructions per second and help avoid stuttering.",
                    "type": "bool",
                    "default_value": true
                },
                "maxPerSec":
                {
                    "label": "Maximum per Second",
                    "description": "The maximum number of gCode instructions per second that your printer is capable of processing.\\n\\nThe feed rate of extrusion segments will be reduced, subject to the minimum print speed below, in order that the printing time for the segment is at least 1/max-per-sec long.",
                    "enabled": "enabled",
                    "type": "int",
                    "unit": "/s",
                    "minimum_value": 1,
                    "minimum_value_warning": 10,
                    "default_value": 50
                },
                "minPrintSpeed":
                {
                    "label": "Minimum print speed",
                    "description": "Minimum print speed - this script will not slow the print speed below this amount.\\n\\nNote: Machine minimum print speed is always respected, and if Print Cooling is enabled then the minimum print speed for cooling is also always respected.",
                    "enabled": "enabled",
                    "type": "float",
                    "unit": "mm/s",
                    "default_value": 0.0,
                    "minimum_value": 0.1,
                    "minimum_value_warning": 0
                },
                "verbose":
                {
                    "label": "Verbose gCode?",
                    "description": "Add existing gCode as a comment so you can see the changes",
                    "enabled": "enabled",
                    "type": "bool",
                    "default_value": false
                },
                "debug":
                {
                    "label": "Debug layers?",
                    "description": "Number of layers to debug to Cura log?",
                    "enabled": "enabled",
                    "type": "int",
                    "default_value": 0
                }
            }
        }""")

    def getSettingProperty(self, key: str, prop: str) -> Any:
        """Convenience function that retrieves a specified attribute of a setting from the stack."""

        if self._stack is None:
            Logger.log("e", "gCodePerSec: getSettingProperty: Unable to get stack.")
            return None

        result = self._stack.getProperty(key, prop)
        if result is None:
            Logger.log("e", "gCodePerSec: getSettingProperty: Failed to get " + key + "." + prop + ".")
        return result

    def getSettingValueByKey(self, key: str) -> Any:
        """Convenience function that retrieves a specified attribute of a setting from the stack."""

        return self.getSettingProperty(key, "value")

    def setSettingProperty(self, key: str, prop: str, value: Any) -> bool:
        """Convenience method that sets the attrribute of a setting on the stack."""

        if self._instance is None:
            Logger.log("e", "gCodePerSec: setSettingProperty: Unable to get instance.")
            return False

        self._instance.setProperty(key, prop, value)

        if self.getSettingProperty(key, prop) != value:
            Logger.log("e", "gCodePerSec: setSettingProperty: Failed to set " + key + "." + prop + " to " + str(value) + ".")
            return False
        return True

    def initialize(self) -> None:
        super().initialize()
        Logger.log("d", "gCodePerSec: initialize called.")

        # Get various settings from global stack so we can use their values as defaults
        # We get these here so that we get the current values at the time that the settings dialog is displayed
        global_container_stack = Application.getInstance().getGlobalContainerStack()
        if global_container_stack is None:
            Logger.log("e", "gCodePerSec: getSettingDataString: Unable to get global container stack.")
            return

        machine_minimum_feedrate  = global_container_stack.getProperty("machine_minimum_feedrate", "value")
        cool_fan_enabled          = global_container_stack.getProperty("cool_fan_enabled", "value")
        cool_min_speed            = global_container_stack.getProperty("cool_min_speed", "value")
        minPrintSpeed_default     = max(cool_min_speed, machine_minimum_feedrate) if cool_fan_enabled else machine_minimum_feedrate
        Logger.log("d", "gCodePerSec: machine_minimum_feedrate = " + str(machine_minimum_feedrate))
        Logger.log("d", "gCodePerSec: cool_fan_enabled = " + str(cool_fan_enabled))
        Logger.log("d", "gCodePerSec: cool_min_speed = " + str(cool_min_speed))
        Logger.log("d", "gCodePerSec: minPrintSpeed_default = " + str(minPrintSpeed_default))

        Logger.log("d", "gCodePerSec: minPrintSpeed minimum_value_warning = " + str(minPrintSpeed_default))
        # At the time of writing, saving the minimum_value_warning doesnt work.
        self.setSettingProperty("minPrintSpeed", "minimum_value_warning", minPrintSpeed_default)
        #Logger.log("d", "gCodePerSec: minPrintSpeed minimum_value = " + str(minPrintSpeed_default))
        #self.setSettingProperty("minPrintSpeed", "minimum_value", minPrintSpeed_default)
        if self.getSettingValueByKey("minPrintSpeed") == 0.0: # Default and invalid value
            self.setSettingProperty("minPrintSpeed", "value", minPrintSpeed_default)
            Logger.log("d", "gCodePerSec: minPrintSpeed value = " + str(minPrintSpeed_default))

    def execute(self, data: List[str]) -> List[str]:

        Logger.log("i", "gCodePerSec: Execute.")
        enabled = self.getSettingValueByKey("enabled")
        if not enabled:
            Logger.log("i", "gCodePerSec: Disabled - no action taken.")
            return data

        TIME_ELAPSED = ";TIME_ELAPSED:"

        # Get various settings from global stack so we can use their values as defaults
        # We get these here so that we get the current values at the time that the settings dialog is displayed
        global_container_stack = Application.getInstance().getGlobalContainerStack()
        if global_container_stack is None:
            Logger.log("e", "gCodePerSec: getSettingDataString: Unable to get global container stack.")
            return

        machine_minimum_feedrate  = global_container_stack.getProperty("machine_minimum_feedrate", "value")
        cool_fan_enabled          = global_container_stack.getProperty("cool_fan_enabled", "value")
        cool_min_speed            = global_container_stack.getProperty("cool_min_speed", "value")
        minPrintSpeed_default     = max(cool_min_speed, machine_minimum_feedrate) if cool_fan_enabled else machine_minimum_feedrate

        maxPerSec     = max(1, self.getSettingValueByKey("maxPerSec"))
        minSegmentTime = 1 / float(maxPerSec)
        minPrintSpeed = max(0.1, self.getSettingValueByKey("minPrintSpeed"), minPrintSpeed_default)
        minFeedRate = floor(float(minPrintSpeed) * 60)
        verbose = self.getSettingValueByKey("verbose")
        debug = self.getSettingValueByKey("debug")

        if debug:
            Logger.log("d", "gCodePerSec: getSettingDataString: \n" + self.getSettingDataString())
            Logger.log("d", "gCodePerSec: maxPerSec = " + str(maxPerSec) + "/s")
            Logger.log("d", "gCodePerSec: minSegmentTime = " + str(minSegmentTime) + "s")
            Logger.log("d", "gCodePerSec: minPrintSpeed = " + str(minPrintSpeed) + "mm/s")
            Logger.log("d", "gCodePerSec: minFeedRate = F" + str(minFeedRate))
            Logger.log("d", "gCodePerSec: verbose = " + str(verbose))
        Logger.log("d", "gCodePerSec: Debug layers = " + str(debug))

        feedrate = None
        prev_x = prev_y = None
        adjusted_feedrate = None
        extra_time = 0.0
        for layer_no, layer in enumerate(data):
            if layer_no == 1:
                layer = ";Postprocessed by gCodePerSec: max gCode per sec = " + str(maxPerSec) + "/s, min print speed = " + str(minPrintSpeed) + "mm/s\n" + layer
            lines = layer.split("\n")
            for line_no, line in enumerate(lines):
                new_line = None
                # Add script settings to gCode
                if line.startswith("G0 ") or line.startswith("G1 "):

                    # Not all G0 G1 contain feedrates - they use the previous one if omitted, so we need to save it - and restore it if we have overwritten it.
                    f = self.getValue(line,"F")
                    if f:
                        feedrate = int(f)
                        if debug:
                            Logger.log("d", "gCodePerSec: Processing layer " + str(layer_no) + " line " + str(line_no) + ": " + line)
                            Logger.log("d", "gCodePerSec: Saving feedrate: F" + str(feedrate))

                    x = self.getValue(line,"X")
                    y = self.getValue(line,"Y")
                    if x and y and prev_x and prev_y:
                        distance = sqrt((x - prev_x) ** 2 + (y - prev_y) ** 2)
                        time = distance / float(feedrate) * 60.0
                        if debug:
                            if not f:
                                Logger.log("d", "gCodePerSec: Processing layer " + str(layer_no) + " line " + str(line_no) + ": " + line)
                            Logger.log("d", "gCodePerSec: Distance: " + str(distance) +"mm, Time: " + str(time) + "ms, " + ("<" if time < minSegmentTime else ">=") + " minimum")

                        if distance > 0 and time < minSegmentTime:
                            new_feedrate = max(floor(minSegmentTime / distance * 60), minFeedRate)
                            if verbose or new_feedrate != adjusted_feedrate:
                                new_line = self.putValue(line, F = new_feedrate)
                            extra_time += (distance / float(new_feedrate) * 60.0) - time
                            adjusted_feedrate = new_feedrate
                        elif adjusted_feedrate:
                            new_line = self.putValue(line, F = feedrate)
                            adjusted_feedrate = None
                    if x:
                        prev_x = x
                    if y:
                        prev_y = y
                elif line.upper().startswith(TIME_ELAPSED):
                    if debug:
                        Logger.log("d", "gCodePerSec: Processing layer " + str(layer_no) + " line " + str(line_no) + ": " + line)
                    new_line = TIME_ELAPSED + str(round(float(line.lstrip(TIME_ELAPSED)) + extra_time,6))
                if new_line:
                    if debug:
                        Logger.log("d", "gCodePerSec: New line: " + new_line)
                    if verbose:
                        lines[line_no] = "; " + line + "\n" + new_line
                    else:
                        lines[line_no] = new_line

            if debug:
                debug -= 1
                if not debug:
                    Logger.log("d", "gCodePerSec: Debug ended.")

            data[layer_no] = "\n".join(lines)

        if extra_time > 0.0:
            data[-1] = ";Postprocessed by gCodePerSec: Additional print time to avoid stuttering = " + str(timedelta(seconds = floor(extra_time))) + "hms\n" + data[-1]

        return data
