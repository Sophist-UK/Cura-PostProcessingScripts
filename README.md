# Cura-PostProcessingScripts

This is a repository of Cura PostProcessings scripts written or modified by Sophist.

## gCodePerSec script
Many 3D printers have gCode processors which are of limited computing power, or which have limited bandwidth for 
accepting instructions from network or USB communications from e.g. Octoprint or Cura USB drivers -
particularly those Printers whose firmware runs on 8-bit processors (like mines). 
As a consequence when Cura tries to print curves using hundreds or even thousands of very small straight line 
segments, the printer cannot receive the gCode instructions fast enough, and it stutters - 
and when it stutters, molten filament can ooze from the print head leading to blobs or "zits" or other quality issues. 
Stuttering is uncontrolledand unwanted behaviour that leads to poor print quality.

Cura has some Mesh Enhancements settings to help preven this i.e. Maximum Resolution, Maximum Deviation -
which are designed to convert several short segments that are almost but not quite in line with each other into
a single longer straight line segment that doesn't deviate too much from the original path.
Typically you set the maximum deviation to a small fraction of a mm (say 1/20 mm or 0.05mm) because this level of 
deviation is almost too small to notice, and this can be very effective on curves that are not too tight.
Maximum Resolution / Maximum Deviation should be your first choice to reduce stuttering.

However, tight curves are less amenable to this Mesh Enhancement, and stuttering can still occur.

The gCodePerMin Cura post-processing script is a complementary approach to the above Mesh Enhancements,
using an entirely different approacg which can be combined with the Mesh Enhancements. 
In simple terms it prevents stuttering not by combining multiple small line segments into a single bigger one,
but instead by slowing down the print head feedrate to allow more time for the next command to be received.
Used by itself instead of Mesh Enhancements, it simply slows down the huge number of extremely small segments, 
and because these extremely small segments can be printed in a very short time, it needs to slow the printing down a lot.
So this script is best used in conjuction with the Mesh Enhancements.

The scripts can be found [here](https://github.com/Sophist-UK/Cura-PostProcessingScripts/tree/master/gCodePerSec).
**Download the gCodePerSec.py file and store it in the `scripts` subdirectory of the directory opened using  
the Cura menu item Help / Show Configuration Folder.**

The script has the following settings:

* **Enabled** - You can clear this check box to disable the script without removing it from the list of PostProcessings scripts.
* **Maximum per Second** - The maximum number of gcode instructions that can be executed per second on your printer. 
(*See below for information on how to determine this value.)*
* **Minimum print speed** - The minimum speed in mm/s that your printer can print a smooth extrusion.
* **Verbose** - This should normally be cleared in order to make the minimum changes to the gCode produced by Cura.
If you check this item, then whenever the print speed is reduced, the original gCode is added as a comment -
this can make the gCode file substantially bigger.
* **Debug** - The number of layers for which gCodePerSec should give detailed debugging information in the Cura Log for any changes it makes.

### Version history
v0.1.0 - Initial version using a simple approach considering only G0 and G1 line segments and considering them singly in isolation from surrounding gCode.
Because it doesn't consdier surrounding gCode a short line segment between two longer line segments can result is rapid and repeated slow-down/speed-up 
which is detrimental to print quality compared to a more averaged approach. 

### Determining the *Maximum per Second* setting
The current v0.1.0 of the script, simply attempts to make the time required to print each line segment to be 
at least enough time for the next gCode instruction to be downloaded.
Thus for your specific printer you need to know just how many G0 / G1 line segments can be printed per second.
As a simplistic measurement / guide, a simple gCode file is provided to time how long it takes to process 1,000
of the smallest possible (i.e. zero-length) G0 line segments.
If you have a display, or can see in a terminal window (e.g. in Octoprint) the gCode responses, 
then an M31 command will display the time that the script took to run.
Otherwise, you need to use a stopwatch.

If you divide 1,000 by the time taken for the script to run and then round this down a bit, you should
have a reasonable approximation of the number of gCode instructions that **your** printer can process per second.
*(As an example, my Dagoma DiscoEasy200 use an MKS Base 1.5 8-bit processor, and this took c. 18s to run the script.
1,000 / 18 = 55.5, so rounding this down I used a Maximum per Second value of 50.)*

### Initial testing results
As a test of the newly written script, I printed a 5cm ring (saved as a high-resolutions STL to generate a large number of small segments) four times:
* Without Max Resolution / Max Deviation and without gCodePerSec
* Without Max Resolution / Max Deviation and **with** gCodePerSec
* **With** Max Resolution / Max Deviation and without gCodePerSec
* **With** Max Resolution / Max Deviation and **with** gCodePerSec

Without either enhancement, as expected there was a lot of stuttering, and the resulting oozing created many significant surface imperfections "zits".

Running just the gCodePerSec script, the printer ran at the Minmum Speed setting of 10mm/s almost full time. The surface quality was significantly better, 
but still not as good as it could have been, but the print time was greatly extended.

With Max Resolution (1mm) / Max Deviation (0.05mm), but without gCodePerSec, the print was both fast and high quality. 
The print speed was perhaps a little variable (subjectively difficult to be sure just how much), 
and whilst it probably was minor stuttering, you would be hard pressed to recognise it as such without knowing in advance.
The deviation of at most 1/20 mm was not noticeable, and the surface quality was excellent.

Running with both the above Max Resolution / Max Deviation settings and gCodePerSec, would ideally have prevented the remaining stutters and
improved the surface quality still further, however in practice the almost unnoticeable stuttering was replaced by highly variable print speeds 
where a short segment (which was slowed) was bracketed by longer segments that ran at full speed, and this actually resulted in slightly lower print quality.

This version of the script has been provided here for others to experiment with depsite these results.

**Conclusion:** The algorithm needs improving for v0.2.0 to take into account that the 
firware accepts more than a single gCode instruction in advance of the currently printing one, 
and taking advantage of this to smooth out the print speed changes between segments. 
(Detailed algorithm yet to be decided.)

## Hot and Cold script
This script is still in the early stages of development. It is predicated on the following rules of thumb:

1. You get better surface quality, and better bridginbg and overhangs, 
when the extruded filament is cooled quickly to below the glass point - 
by having the cooling fan on high, and possibly by extruding at a slightly lower temperature.

2. You get better adhesion, both horizontally between walls and vertically between layers, 
when the extruded filament remains molten for longer and therefore has more time to fuse with the surrounding plastic -
and for this you want the cooling fan off, and possibly extrude at a slightly higher termperature.

These can be translated into some control rules:

a. Outer walls, top/bottom skins, supports, bridging - Fan full, slightly lower temperature.
b. Inner walls, top/bottom surfaces, infill - Fan off, slightly higher temperature.

Ideally you need to have access to the polygons in order to e.g. determine overhangs, 
so achieving these cooling fan / temperature changes in a postprocessing script based only on 
e.g. Cura's comments about extrusion type,
is going to be significantly more difficult.
However, even if you cannot determine all of the above extrusion types from the Cura comments,
it should be possible to achieve these benefits for some extrusion types using a post processing script,
and this script could serve as a proof of concept before delivering these controls as mainstream code in Cura Engine.

As and when this script is ready to test, it will be added here.
