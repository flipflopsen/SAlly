import TextBlueprint from "./classes/text-blueprint";
import joinPath from "./functions/join-path";

// global variables which can be changed

// constants that have to do with automated grid-drawing
export const AUTOSCALEELEMENTS = true;
export const MAXITERATIONS = 20; // for the drawing algorithm
export const MAINGRIDSTARTGRIDCOOR = {x: 30.5, y: 0.5};

// everything that has to do with pagesize
export const MAX_ZOOM = 4;
export const MIN_ZOOM = 1;
export const ZOOM_STEPS = 0.05 * MAX_ZOOM; // for each scroll how much the page is zoomed in/out
// everything that has to do with scaling the drawings
export const GRIDSIZE = 15 * MAX_ZOOM;
export const ELEMENTSIZE = GRIDSIZE * 2;
export const MINELEMENTDISTANCE = GRIDSIZE * 2;
export const MINELEMENTSIZE = ELEMENTSIZE / 2;
export const MINLINETHICKNESS = 1 * MAX_ZOOM;
export const MAXLINETHICKNESS = ELEMENTSIZE / 3;
export const DRAGGINGACCELERATION = 2; // when dragging how much the canvas moves divided by how much your mouse must move
// constants for click-on and hover-on
export const SHOWLOAD = true; // is then visible on hover
export const SHOWVOLTAGE = true; // is then visible on hover
export const CLICKTEXT = new TextBlueprint("Calibri", GRIDSIZE, "blue");
export const CLICKTEXTDISTANCETOOBJECT = GRIDSIZE;
export const HOVERTEXT = new TextBlueprint("Calibri", GRIDSIZE, "green");
export const TEXTDISTANCETOOBJECT = GRIDSIZE / 3;
export const LINEBREAKDISTANCE = GRIDSIZE / 3;
export const SELECTBORDERSIZE = GRIDSIZE / 3; // in pixels
// constants for always-visible text
export const SHOWIDS = true; // will put the IDs on top of the objects, is then always visible
export const ANOMALYTEXT = new TextBlueprint("Calibri", GRIDSIZE * 3, "red"); // for anomaly-detected "text" (a big exclamation mark)
export const IDTEXTDISTANCETOOBJECT = GRIDSIZE / 15; // for the names of the components
export const IDTEXT = new TextBlueprint("Calibri", GRIDSIZE / 2.3, "grey");  // for the names of the components
export const DEFAULTCABLETHICKNESS = GRIDSIZE / 4;
//constants for edit mode
export const EDITMODETEXT = new TextBlueprint("Calibri", GRIDSIZE, "red");  // for the names of the components


// colors
export const BACKGROUNDCOLOR = "rgba(0, 0, 0)";
export const DEFAULTELEMENTCOLOR = "white"; // only relevant for elements that do not have an image
export const SELECTBORDERCOLOR = "blue";
export const SELECTOPACITY = 1.0;
export const DEFAULTOPACITY = 0.6; // must be smaller than 1.0 so that selected elements appear a bit brighter
export const DEFAULTCABLECOLOR = "grey";
export const LOADINDICATORCOLOR = "red"; // for the red tint on overloaded components


// images
export const IMAGEFOLDER = joinPath("assets", "grid-assets", "images_for_technicans"); // choose between "images_for_technicans" and "images_for_layman"
export const trafo_img_src = joinPath(IMAGEFOLDER, "trafo.png");
export const load_img_src = joinPath(IMAGEFOLDER, "load.png");
export const generator_img_src = joinPath(IMAGEFOLDER, "generator.png");
export const ext_grid_img_src = joinPath(IMAGEFOLDER, "ext_grid.png");
export const bus_img_src = joinPath(IMAGEFOLDER, "bus.png");
export const switch_img_src = joinPath(IMAGEFOLDER, "switch.png");
export const overvoltage_img_src = joinPath(IMAGEFOLDER, "lightning_bolt_red.png");
export const undervoltage_img_src = joinPath(IMAGEFOLDER, "lightning_bolt_blue.png");


// functional variables
export const USE_CIM_LAYOUT = false; // only functional if no saved layout is present
export const CLICKONLYONE = true; // if elements hitboxes overlap, only click one element or all of them?
export const LOADINGDELAY = 5; // a delayin ms so that there is enough time for all the images to load
export const MINIMUMCHANGEFORDRAG = 1; // in pixels, mouse must move at least this much so that a drag event is triggered
export const SHOWDEBUGGINGINFO = false; // if true prints more information in the console
export const BE_STATIC = false; // makes GridView static, so there are no dynamic values displayed
// constants for red-tint on big loads
export const LOADINDICATOROFFSET = 85; // the load in % at which the element starts to get red
export const MAXIMUMLOAD = 200; // in percent
// constants for voltage-dependent events
export const MINVOLTAGE = 0.85; // since voltage is in per-unit, this is in percent
export const MAXVOLTAGE = 1.15;
export const NUMPRINTEDDECIMALS = 2; // so that the displayed values are roundet to 2 decimal places
