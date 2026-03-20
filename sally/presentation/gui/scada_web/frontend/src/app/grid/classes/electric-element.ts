import BasicElectricElement from "./basic-electric-element";
import Vector2D from "./vector-2d";
import drawText from "../functions/draw-text";
import fastDrawImage from "../functions/fast-draw-image";
import State from "../state";

import * as SETTINGS from "../settings";

export default class ElectricElement extends BasicElectricElement {
  dockPosOffset: Vector2D;
  dockPos: Vector2D | null;
  outDockPos: Vector2D | null;

  constructor(
    state: State,
    pos: Vector2D,
    mySize: Vector2D,
    public img: HTMLImageElement | null = null,
    descriptor = "unnamed",
    cim_id: string,
    public rotate = 0
  ) {
    // info: rotations are clockwise
    super(state, pos, mySize, descriptor, cim_id);

    // trafos got 2 docking ports, they have an input and an output port
    // default: output port is on TOP of the object, input port BELOW
    this.dockPosOffset = new Vector2D(this.size.x / 2, this.size.y);

    this.dockPos = null; // is set in evalDockingPortPos()
    this.outDockPos = null; // is set in evalDockingPortPos()
    // update docking port positions
    this.evalDockingPortPos();
    this.init();
  }

  evalDockingPortPos() {
    // default first
    this.dockPos = this.pos.plus(this.dockPosOffset);
    this.outDockPos = new Vector2D(this.dockPos.x, this.dockPos.y - this.dockPosOffset.y);

    if (this.rotate == 0) return;
    // rotate docking port coordinates around the center of the element
    let deltaVector = this.dockPos.minus(this.center).rotate(this.rotate);
    this.dockPos = this.center.plus(deltaVector);
    // output port shall be on the opposite side of the center.
    // Adjust it accordingly
    this.outDockPos = this.center.minus(deltaVector);
  }

  init() {
    // not done in the constructor, so that elements which inherit from this
    // class can go in different arrays
    this.state.electricComponentsArray.push(this);
  }

  drawID() {
    // print the objects-IDs above the image of the object
    drawText(
      this.state,
      "ID: " + this.id,
      SETTINGS.IDTEXT,
      this.pos.x,
      this.pos.y - SETTINGS.IDTEXTDISTANCETOOBJECT - SETTINGS.SELECTBORDERSIZE
    );
  }

  override drawCustom() {
    if (SETTINGS.SHOWIDS) this.drawID();

    if (this.img == null){
      // drop back to the default method of your parent
      super.drawCustom();
      return;
    }

    if (this.rotate == 0) {
      fastDrawImage(
        this.state.bufferContext,
        this.img,
        this.pos.x,
        this.pos.y,
        this.size.x,
        this.size.y
      );
      return;
    }

    // respect rotation
    this.state.bufferContext.setTransform(1, 0, 0, 1, this.center.x, this.center.y); // look at everything from the center of the image
    this.state.bufferContext.rotate(this.rotate * Math.PI / 180); // rotate the whole context. Remember to rotate in radians!
    // Draw the image. We draw images from their left corner onwards --> if the center of the image is (0,0) that is at (-imgWidth/2, imgHeight/2)
    fastDrawImage(
      this.state.bufferContext,
      this.img,
      -this.size.x / 2,
      -this.size.y / 2,
      this.size.x,
      this.size.y
    );
    this.state.bufferContext.setTransform(1, 0, 0, 1, 0, 0); // rotate back to default view
  }
}
