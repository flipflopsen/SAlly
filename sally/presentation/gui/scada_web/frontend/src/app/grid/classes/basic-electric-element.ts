import Vector2D from "./vector-2d";
import TextBlueprint from "./text-blueprint";
import giveID from "../functions/give-id";
import fastDrawImage from "../functions/fast-draw-image";
import drawText from "../functions/draw-text";
import drawRectangle from "../functions/draw-rectangle";
import State from "../state";

import * as SETTINGS from "../settings";

export default class BasicElectricElement {	// base-model for all the other classes
  pos: Vector2D;
  size: Vector2D;
  center: Vector2D;
  descriptor: string;
  cim_id: string;
  id: number; // an easier to read ID than CIM-ID. Helps with debugging.

  allowTextBoxDraw = true;
  isClicked = false;
  isHovered = false;
  hasAnomaly = false;
  voltageTooLow = false;
  voltageTooHigh = false;
  loading_percent = 0;
  voltage_pu = 0;
  activePower_mw = 0;
  reactivePower_var = 0;
  maxApparentPower_va = 0;
  voltageToCurrentAngle = 0;
  switchInService = true; // only relevant for switches
  switchClosed = true; // only relevant for switches
  editModeBorderMarker1 = false;
  editModeBorderMarker2 = false;
  typeDescriptor = "unamed";

  constructor(
    public state: State,
    pos: Vector2D,
    mySize: Vector2D,
    descriptor = "unnamed",
    cim_id: string,
  ) {
    this.pos = pos.copy(); // pos.x & pos.y decribe the upper left corner of the hitbox of the object
    this.size = mySize.copy(); // pos.x+mySize.x & pos.y+mySize.y decribes the lower right corner of the hitbox of the object
    this.center = this.pos.plus(this.size.mult(0.5)); // center-coordinate of the object
    this.cim_id = cim_id;
    this.descriptor = descriptor;
    this.id = giveID(this.descriptor);
  }


  draw() {
    this.checkVoltage(); // update voltage-events

    this.state.bufferContext.globalAlpha = SETTINGS.DEFAULTOPACITY;
    this.state.bufferContext.beginPath(); // begin a new path for every object you draw so that they are handeled one by one
        
    if (this.isClicked || this.isHovered) {
      this.state.bufferContext.globalAlpha = SETTINGS.SELECTOPACITY;
    }
    
    if (this.isClicked) {
      // draw a rectangle behind the image
      this.drawBorder(SETTINGS.SELECTBORDERSIZE, SETTINGS.SELECTBORDERCOLOR);
    }

    if (this.editModeBorderMarker1) {
      this.drawBorder(SETTINGS.SELECTBORDERSIZE*1, "yellow");
    }
    if (this.editModeBorderMarker2) {
      this.drawBorder(SETTINGS.SELECTBORDERSIZE*2, "red");
    }

    this.drawCustom(); // this method can be overwritten by child classes
    this.loadIndicator(); // makes element reddish depending on the load
    this.voltageIndicator(); // draws lightning bolts in various colors on top of the element if voltage band is violated
  }

  drawBorder(borderWidth: number, borderColor: string){
    this.state.bufferContext.lineWidth = borderWidth;
    this.state.bufferContext.strokeStyle = borderColor;
    // make sure it has some distance to the image by SELECTBORDERSIZE in all directions
    this.state.bufferContext.strokeRect(
      this.pos.x - borderWidth,
      this.pos.y - borderWidth,
      this.size.x + 2 * borderWidth,
      this.size.y + 2 * borderWidth,
    );
  }

  checkVoltage() {
    this.voltageTooLow = false;
    this.voltageTooHigh = false;
    // check voltage level
    if (this.descriptor !== "bus"){return;}

    if (this.voltage_pu < SETTINGS.MINVOLTAGE) {
      // under-voltage event
      this.voltageTooLow = true;
      this.voltageTooHigh = false;
      return;
    }

    if (this.voltage_pu > SETTINGS.MAXVOLTAGE) {
      // over-voltage event
      this.voltageTooLow = false;
      this.voltageTooHigh = true;
      return;
    }
  }

  voltageIndicator() {
    // only valid for busses/nodes

    // draw on top of the image a yellow lightning strike if voltage is too low
    // or too high but if this is a cable we should not do it

    if (this.typeDescriptor !== "bus") return;

    let img;
    if (this.voltageTooLow) img = this.state.undervoltageImg;
    if (this.voltageTooHigh) img = this.state.overvoltageImg;

    if (img) fastDrawImage(
      this.state.bufferContext,
      img,
      this.pos.x,
      this.pos.y,
      this.size.x,
      this.size.y
    );
  }

  getText2Draw() {
    // textArray stores the different pieces of text and their text-style
    let textArray: [string, TextBlueprint][] = [];

    if (this.hasAnomaly) {
      // draw a big red exclamation mark
      textArray.push(["!", SETTINGS.ANOMALYTEXT]);
    }
    
    if (this.isHovered || this.isClicked) {
      // textArray.push(["CIM ID: " + this.cim_id, SETTINGS.HOVERTEXT]);
      textArray.push([this.descriptor, SETTINGS.HOVERTEXT]);
      
      if (!SETTINGS.BE_STATIC && !this.state.editMode)  {
        if (SETTINGS.SHOWLOAD && this.isLoadable() && (this.cim_id != "standard connection")) {
          let loadFixed = this.loading_percent.toFixed(SETTINGS.NUMPRINTEDDECIMALS);
          textArray.push([`load: ${loadFixed}%`, SETTINGS.HOVERTEXT]);
        }
  
        if (SETTINGS.SHOWVOLTAGE && (this.typeDescriptor == "bus")) {
          let voltageFixed = this.voltage_pu.toFixed(SETTINGS.NUMPRINTEDDECIMALS);
          textArray.push([`U: ${voltageFixed}pu`, SETTINGS.HOVERTEXT]);
        }
        if ((this.typeDescriptor == "load" || this.typeDescriptor == "generator" || this.typeDescriptor == "bus")) {
          let p_mw_Fixed = this.activePower_mw.toFixed(SETTINGS.NUMPRINTEDDECIMALS);
          let q_mwar_Fixed = this.reactivePower_var.toFixed(SETTINGS.NUMPRINTEDDECIMALS);
          textArray.push([`P: ${p_mw_Fixed}mw`, SETTINGS.HOVERTEXT]);
          textArray.push([`Q: ${q_mwar_Fixed}mvar`, SETTINGS.HOVERTEXT]);
        }
        // have to explain the big red exclamation mark if it is present
        if (this.hasAnomaly) {
          textArray.push(["Anomaly detected!", SETTINGS.HOVERTEXT]);
        }
      }
    }

    return textArray;
  }

  textBoxDraw() {
    if(!this.allowTextBoxDraw){
      return;
    }
    let textArray = this.getText2Draw();

    // now determine how to position the text
    // the info-box starts in the top-right corner of the element by default
    let offset = new Vector2D(
      this.pos.x + this.size.x + SETTINGS.TEXTDISTANCETOOBJECT + SETTINGS.SELECTBORDERSIZE,
      this.pos.y
    );
    // How much space is needed? Get total height of the text!
    let summedYOffset = 0;
    for (let textEl of textArray) {
      summedYOffset += SETTINGS.LINEBREAKDISTANCE + textEl[1].fontSize;
    }
    // if you have the space to spare, start the text to the right of the object
    // and center around the middle
    if (summedYOffset < Math.abs(this.size.y)) {
      // calculate where you can begin to draw the text
      offset.y = this.pos.y + (this.size.y - summedYOffset) / 2;
    }
    summedYOffset = 0; // reset offset

    // if object is a wire we may want to position the infobox differently
    if (this.typeDescriptor == "wire") {
      // find the long side of the wire
      if (Math.abs(this.size.x) <= Math.abs(this.size.y)) { //size can be negative for wires! respect that!
        // vertical wire, can be trated like normal element
      } else {
        // horizontal wire --> write infobox below the wire in the middle
        offset.y = this.pos.y + SETTINGS.TEXTDISTANCETOOBJECT + SETTINGS. SELECTBORDERSIZE;
        offset.x = this.pos.x + this.size.x / 2;
      }
    }

    // now draw line by line
    this.state.bufferContext.globalAlpha = SETTINGS.SELECTOPACITY;
    for (let [text, blueprint] of textArray) {
      drawText(
        this.state,
        text,
        blueprint,
        offset.x,
        offset.y + blueprint.fontSize + summedYOffset
      );
      summedYOffset += SETTINGS.LINEBREAKDISTANCE + blueprint.fontSize;
    }
  }

  isLoadable(){
    // "standard cables", "external grid", "bus", "generator" and "load" have no loading-percentage
    if (
    this.typeDescriptor == "generator" ||
    this.typeDescriptor == "load" ||
    // this.typeDescriptor == "cable" ||
    this.typeDescriptor == "wire" ||
    this.typeDescriptor == "trafo"){
      return true;
    }
    return false;
  }

  drawCustom() {
    // method that can be overwritten by child classes
    // default: draw a rectangle which has the size of this object
    // (this default setting is actually used by the wires)
    drawRectangle(
      this.state,
      this.pos.x,
      this.pos.y,
      this.size.x,
      this.size.y,
      SETTINGS.DEFAULTELEMENTCOLOR
    )
  }

  // draw a red rectangle on top depending on the load
  loadIndicator() {
    if(!(this.isLoadable())){
      return;
    }
    // only draw the rectangle when a certain threshold is reached
    if (this.loading_percent <= SETTINGS.LOADINDICATOROFFSET) return;
    // scale opacity between 0 and 1
    let opacity = (this.loading_percent - SETTINGS.LOADINDICATOROFFSET) / (SETTINGS.MAXIMUMLOAD - SETTINGS.LOADINDICATOROFFSET);
    opacity = Math.min(opacity, 1);
    this.state.bufferContext.globalAlpha = opacity;
    //this.state.bufferContext.globalCompositeOperation = "multiply"; // enables to ignore transparent pixels
    drawRectangle(
      this.state,
      this.pos.x,
      this.pos.y,
      this.size.x,
      this.size.y,
      SETTINGS.LOADINDICATORCOLOR
    )
    //this.state.bufferContext.globalCompositeOperation = "source-over"; // back to default
  }

  isCoorInHitbox(coor: Vector2D) {

    // the hitbox starts at this.x and this.y and ends at this.x + this.sizeX and this.y+this.sizeY
    // we check if the given coordinate is inside the rectangle which is drawn by these two points
    // however: use translated x & y to respect scaling
    // let hit = false;
    // is the given coordinate between the two corner coordinates of this element?
    let latePos = this.pos.copy();
    let leadingPos = this.pos.plus(this.size);
    // size can be negative! Need to check which really is the leading/top coordinate
    if (this.size.x < 0) {
      // switch them
      latePos.x = leadingPos.x;
      leadingPos.x = this.pos.x;
    }
    if (this.size.y < 0) {
      // switch them
      latePos.y = leadingPos.y;
      leadingPos.y = this.pos.y;
    }

    if ((latePos.x < coor.x) && (coor.x < leadingPos.x)) {
      if ((latePos.y < coor.y) && (coor.y < leadingPos.y)){
        return true;
      }
    }

    return false;
  }

  clickAction() {
    this.isClicked = true;
  }

  unClickAction() {
    this.isClicked = false;
  }

  hoverAction() {
    this.isHovered = true;
  }

  unHoverAction() {
    this.isHovered = false;
  }
}
