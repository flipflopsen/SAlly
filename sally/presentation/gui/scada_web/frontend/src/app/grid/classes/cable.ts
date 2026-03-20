import ElectricElement from "./electric-element";
import VisibleWire from "./visible-wire";
import Vector2D from "./vector-2d";
import StructuredElement from "./structured-element";
import State from "../state";

import * as SETTINGS from "../settings";

export default class Cable extends ElectricElement { // sums up multiple VisibleWire's into one entity
  // contains in order the connected pieces of VisibleWire which display this wire
  visibleWireArray: VisibleWire[] = [];
  visibleWireInHitBox: VisibleWire;

  halfCableThickness = SETTINGS.DEFAULTCABLETHICKNESS / 2;

  info: Record<string, number>;

  targetDockPos: Vector2D;
  head: Vector2D;

  constructor(
    state: State,
    public startConnectionElem: StructuredElement,
    public endConnectionElem: StructuredElement,
    public startUseOutputPort = false,
    public endUseOutputPort = false,
    max_i_ka: number = 0,
    cim_id: string = "standard connection",
  ) {
    // call parent-constructor with null's because this class comprises multiple
    // elements, but does not have a physical size itself
    // However, we need to inherit the default variables & it executes our
    // init-function + this class simply needs all properties of an
    // ElectricElement because it is one
    super(state, new Vector2D(0, 0), new Vector2D(0, 0), null, "cable", cim_id);
    this.typeDescriptor = "cable";

    this.info = {};
    this.info["max_i_ka"] = max_i_ka;
    this.info["vn_kv"] = 0;
    
    // take the voltage from the bus node you are connected to
    if (startConnectionElem.typeDescriptor == "bus") {
      this.info["vn_kv"] = startConnectionElem.info["vn_kv"];
    } else if(endConnectionElem.typeDescriptor == "bus") {
      this.info["vn_kv"] = endConnectionElem.info["vn_kv"];
    }
    this.maxApparentPower_va = this.info["max_i_ka"] * this.info["vn_kv"]

    // which of the 2 possible ports of the start and end element should
    // actually be used?
    // default
    this.targetDockPos = this.endConnectionElem.dockPos!.copy();
    this.dockPos = this.startConnectionElem.dockPos!.copy();

    // keep track of where the "head" of your connection is when rolling the wire
    this.head = this.dockPos.copy();
    this.rollWire();
    this.visibleWireInHitBox = this.visibleWireArray[0];
  }

  parentUpdate() {
    // execute this funtion if the position of your parents changed
    // which of the 2 possible ports of the start and end element should actually be used?
    type DockPos = "outDockPos" | "dockPos";
    let dockPosConnection: DockPos = this.startUseOutputPort ? "outDockPos" : "dockPos";
    this.dockPos = this.startConnectionElem[dockPosConnection]!.copy();

    let targetDockPosConnection: DockPos = this.endUseOutputPort ? "outDockPos" : "dockPos";
    this.targetDockPos = this.endConnectionElem[targetDockPosConnection]!.copy();

    this.visibleWireArray = [];
    this.head = this.dockPos.copy();
    
    //console.log("parentUpdate - rolling wire");
    this.rollWire();
  }

  happenedParentUpdate() {
    // find out if any of your parents position changed
    if (!this.startUseOutputPort) {
      if (!this.dockPos!.equals(this.startConnectionElem.dockPos!)) return true;
    } else {
      if (!this.dockPos!.equals(this.startConnectionElem.outDockPos!)) return true;
    }
    
    if (!this.endUseOutputPort) {
      if (!this.targetDockPos.equals(this.endConnectionElem.dockPos!)) return true;
    } else {
      if (!this.targetDockPos.equals(this.endConnectionElem.outDockPos!)) return true;      
    }

    return false;
  }

  override init() {
    this.state.cablesArray.push(this);
  }

  private rollWire() {
    // some algorithm which cleverly creates VisibleWire-Objects to display the
    // connection in an electrically correct way just straight up connect the
    // points, but avoid drawing them through source or target hitbox
    // (remember: we don't know about any objects in between. The algorithm
    // which orders the elements ought to check there are non in between)
    let dontMindStart = false; // if start of wire is a bus, no need to go around it
    let dontMindEnd = false; // if end of wire is a bus, no need to go around it
    let targetCoor = this.targetDockPos.copy();
    let sourceCoor = this.dockPos!;
    // get vectors
    let sourceLookVector = sourceCoor.minus(this.startConnectionElem.center);
    let targetLookVector = targetCoor.minus(this.endConnectionElem.center);
    let distanceDelta = targetCoor.minus(sourceCoor);
    // norm vectors
    let sourceLookVectorLength = sourceLookVector.length;
    let targetLookVectorLength = targetLookVector.length;
    if(sourceLookVectorLength > 0){
      sourceLookVector = sourceLookVector.normed();
    } else {
      sourceLookVector.x = 0;
      sourceLookVector.y = 0;
      dontMindStart = true;
    }
    if(targetLookVectorLength > 0){
      targetLookVector = targetLookVector.normed();
    } else {
      targetLookVector.x = 0;
      targetLookVector.y = 0;
      dontMindEnd = true;
    }

    let startOverlap = false;
    if((sourceLookVector.plus(distanceDelta).length < distanceDelta.length) && !dontMindStart){
      startOverlap = true;
    }
    let endOverlap = false;
    if((targetLookVector.minus(distanceDelta).length < distanceDelta.length) && !dontMindEnd){
      endOverlap = true;
    }
    
    let minDist = 0;
    let distToEnd = 0;
    let nextWireVertical = false;
    let currentlyVertical = false;
    if (sourceLookVector.x < sourceLookVector.y){
      currentlyVertical = true;
    }
    if (startOverlap || endOverlap){
      // in this case: first go orthogonal in direction of the target
      // by half an element to go around the starting element
      nextWireVertical = !currentlyVertical;
      minDist = SETTINGS.ELEMENTSIZE / 2;
    }

    if (startOverlap && endOverlap){
      // also need to go around the ending element
      distToEnd = SETTINGS.ELEMENTSIZE / 2;
    }
    nextWireVertical = this.wireAdvance(nextWireVertical, targetCoor, minDist, distToEnd);
    nextWireVertical = this.wireAdvance(nextWireVertical, targetCoor);
    nextWireVertical = this.wireAdvance(nextWireVertical, targetCoor);
  }

  wireAdvance(verticalWire:boolean, targetCoor: Vector2D, minDist: number = 0, distToEnd: number = 0){
    // roll a bit of the wire
    let distToRoll = 0;
    let extraDist = 0;
    if (verticalWire){
      distToRoll = Math.abs(this.head.y - (targetCoor.y - distToEnd))
      if (distToRoll < minDist){
        extraDist = minDist - distToRoll;
      }
      this.rollWireVertical(targetCoor.y + extraDist, true);
    } else {
      distToRoll = Math.abs(this.head.x - (targetCoor.x - distToEnd))
      if (distToRoll < minDist){
        extraDist = minDist - distToRoll;
      }
      this.rollWireHorizontal(targetCoor.x + extraDist, true);
    }
    return (!verticalWire);
  }

  rollWireHorizontal(to_x: number, firstWire = false) {
    // roll wire only on the x-axis --> keep y-axis constant apart from DEFAULTCABLETHICKNESS
    // + make sure that the cable is in the middle

    // only draw a wire, if we are not there yet
    if (this.head.x == to_x) return;
    // first: bring the head in the correct position, so that it neatly fits to any previously drawn wires
    // firstWire == true: move head 1 unit against the direction where to go to close up with the startelement
    // firstWire == false: move head 1 unit in the direction where to go to close up with the last cable that was connected to you
    let move_direction = firstWire ? -1 : 1;
    this.head.x += move_direction * Math.sign(to_x - this.head.x) * this.halfCableThickness;

    // split the cablethickness by moving the two coordinates in different directions by this.halfCableThickness
    // together this will create a rectangle that represents the cable with a thickness of DEFAULTCABLETHICKNESS
    // go in the direction of movement another this.halfCableThickness so that the next wire connects clean to this one
    let newWire = new VisibleWire(
      this.state,
      this.head.minus(new Vector2D(0, this.halfCableThickness)),
      new Vector2D(
        to_x + Math.sign(to_x - this.head.x) * this.halfCableThickness,
        this.head.y+this.halfCableThickness
      ),
      this
    );
    this.visibleWireArray.push(newWire);
    // set head to new position but undo what you did for cablethickness so that
    // we always have a standard-position with regards to the last cable we drew
    this.head = newWire.toPos.minus(new Vector2D(
      Math.sign(to_x - this.head.x) * this.halfCableThickness,
      this.halfCableThickness
    ));
  }

  rollWireVertical(to_y: number, firstWire = false){
    // roll wire only on the y-axis --> keep x-axis constant apart from DEFAULTCABLETHICKNESS
    // + make sure that the cable is in the middle

    // only draw a wire, if we are not there yet
    if (this.head.y == to_y) return;
    // first: bring the head in the correct position, so that it neatly fits to any previously drawn wires
    // firstWire == true: move head 1 unit against the direction where to go to close up with the startelement
    // firstWire == false: move head 1 unit in the direction where to go to close up with the last cable that was connected to you
    let move_direction = firstWire ? -1 : 1;
    this.head.y += move_direction * Math.sign(to_y - this.head.y) * this.halfCableThickness;

    // split the cablethickness by moving the two coordinates in different
    // directions by this.halfCableThickness
    // together this will create a rectangle that represents the cable with a
    // thickness of DEFAULTCABLETHICKNESS
    let newWire = new VisibleWire(
      this.state,
      this.head.minus(new Vector2D(this.halfCableThickness, 0)),
      new Vector2D(
        this.head.x + this.halfCableThickness,
        to_y + Math.sign(to_y - this.head.y) * this.halfCableThickness
      ),
      this
    );
    this.visibleWireArray.push(newWire);
    // set head to new position but undo what you did for cablethickness so that
    // we always have a standard-position with regards to the last cable we drew
    this.head = newWire.toPos.minus(new Vector2D(
      this.halfCableThickness,
      Math.sign(to_y - this.head.y) * this.halfCableThickness
    ));
  }

  // need to overwrite some functions so that the individual wire is called
  override clickAction() {
    this.isClicked = true;
    // also click all visibleWires
    this.visibleWireArray.forEach(wire => {
      wire.ParentClickAction();
    });
    this.visibleWireInHitBox.allowTextBoxDraw = true;
  }

  override unClickAction() {
    this.isClicked = false;
    // also UNclick all visibleWires
    this.visibleWireArray.forEach(wire => {
      wire.ParentUnClickAction();
    });
    this.visibleWireInHitBox.allowTextBoxDraw = false;
  }

  override hoverAction() {
    this.isHovered = true;
    // also hover all visibleWires
    this.visibleWireArray.forEach(wire => {
      wire.ParentHoverAction();
    });
    this.visibleWireInHitBox.allowTextBoxDraw = true;
  }

  override unHoverAction() {
    this.isHovered = false;
    // also UNhover all visibleWires
    this.visibleWireArray.forEach(wire => {
      wire.ParentUnHoverAction();
    });
    this.visibleWireInHitBox.allowTextBoxDraw = false;
  }

  override draw() {
    // if elements were dragged, need to re-roll the wires as well
    // check if the positions of the elements you connect have changed
    if(this.happenedParentUpdate()) this.parentUpdate();
    // draw your visibleWires, pass on your parameters
    this.visibleWireArray.forEach(wire => {
      wire.loading_percent = this.loading_percent;
      wire.hasAnomaly = this.hasAnomaly;
      wire.draw();
    });
  }

  override textBoxDraw() {
    this.visibleWireArray.forEach(wire => {
      wire.textBoxDraw();
    });
  }

  override isCoorInHitbox(coor: Vector2D) {
    for (let visibleWire of this.visibleWireArray) {
      if (visibleWire.isCoorInHitbox(coor)){
        this.visibleWireInHitBox = visibleWire;
        return true;
      } 
    }

    return false;
  }
}
