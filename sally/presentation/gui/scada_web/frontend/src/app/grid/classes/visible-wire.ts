import BasicElectricElement from "./basic-electric-element";
import Vector2D from "./vector-2d";
import drawRectangle from "../functions/draw-rectangle";
import State from "../state";

import * as SETTINGS from "../settings";

// one connection on the screen is made up of multiple ones of these
export default class VisibleWire extends BasicElectricElement {
  constructor(
    state: State,
    fromPos: Vector2D,
    public toPos: Vector2D,
    public parent: BasicElectricElement
  ) {
    super(state, fromPos, toPos.minus(fromPos), "wire", parent.cim_id);
    this.typeDescriptor = "wire";
    this.allowTextBoxDraw = false;
  }

  override drawCustom() {
    drawRectangle(
      this.state,
      this.pos.x,
      this.pos.y,
      this.size.x,
      this.size.y,
      SETTINGS.DEFAULTCABLECOLOR
    );
  }

  // the actions of a visible wire are called by the parent, which is the whole cable
  ParentClickAction() {
    this.isClicked = true;
  }

  ParentUnClickAction() {
    this.isClicked = false;
  }

  ParentHoverAction() {
    this.isHovered = true;
  }

  ParentUnHoverAction() {
    this.isHovered = false;
  }

  // overwrite the "induvidual" methods so that the parent is called instead
  override clickAction() {
    // tell your parent element that you have been clicked, so that it can click all the parts of this cable
    this.parent.clickAction();
  }

  override unClickAction() {
    this.parent.unClickAction();
  }

  override hoverAction() {
    this.parent.hoverAction();
  }

  override unHoverAction() {
    this.parent.unHoverAction();
  }
}
