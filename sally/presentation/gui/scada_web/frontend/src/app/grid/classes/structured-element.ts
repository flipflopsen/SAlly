import ElectricElement from "./electric-element";
import Vector2D from "./vector-2d";
import drawText from "../functions/draw-text";
import State from "../state";
import Cable from "../classes/cable";
import * as SETTINGS from "../settings";


export default class StructuredElement extends ElectricElement {
  reservedSpaceRight = 0;
  reservedSpaceLeft = 0;
  reservedSpaceBelow = 0;

  spaceRightArray: number[] = []; // contains the space-right for each child of this element
  spaceLeftArray: number[] = []; // contains the space-left for each child of this element
  spaceBelowArray: number[] = []; // contains the space-below for each child of this element

  reservedSpaceRightOld = 0;
  reservedSpaceLeftOld = 0;
  reservedSpaceBelowOld = 0;

  children: StructuredElement[] = [];
  stepsAwayFromRootNode = -1; // will be overwritten later

  // the following paramters are set when a parent executes addChild()
  parent: StructuredElement | null = null;
  gridOffsetToParent = new Vector2D(0,0); // parent will set this when he adds the child. This value is from the view of the child!
  indexForParent = 0; // the index of this element in the children-array of its parent
  hasParent = false;
  info: Record<string, any> = {}; 

  constructor(
    state: State,
    image: HTMLImageElement,
    descriptor: string,
    cim_ID: string,
    elementInfo: Record<string, any> = {}, // for any additional info provided by the dbase
    rotate = 0
  ) {
    super(
      state,
      new Vector2D(0, 0),
      new Vector2D(SETTINGS.ELEMENTSIZE, SETTINGS.ELEMENTSIZE),
      image,
      descriptor,
      cim_ID,
      rotate
    )
    this.info = elementInfo;    
    if ("sn_mva" in elementInfo) {
      this.maxApparentPower_va = elementInfo["sn_mva"];
    }
  }

  posChange(deltaVector: Vector2D) {
    // update reference to parent, so that the change does not get resetted if
    // the parent gets moved in editmode
    this.gridOffsetToParent = this.gridOffsetToParent.plus(deltaVector);
    let offsetInPixels = this.gridOffsetToParent.mult(SETTINGS.MINELEMENTDISTANCE);
    // update this elements position and of all its child elements
    if (this.hasParent) this.center = this.parent!.center.plus(offsetInPixels);
    else this.center = offsetInPixels.copy(); // if you have no parent take the canvas origin
      
    // update pos-coordinates with the new center-coordinates
    this.pos = this.center.minus(this.size.mult(0.5));

    // also update docking-port positions
    this.evalDockingPortPos();

    this.children.forEach(child => {
      // let your children update
      child.posChange(new Vector2D(0,0));
    });

    // if(((this.pos.x > this.state.canvas.width) || (this.pos.x < 0)) || ((this.pos.y > this.state.canvas.height) || (this.pos.y < 0))){
    // 	console.log("Element with ID", this.id, "placed outside the canvas. Coordinate: ", this.pos.x, this.pos.y, "type", this.typeDescriptor);
    // }
  }

  getOwnSpaceRequirements() {
    // reserve space for your children if you have any
    if (this.children.length > 0) {
      // find the extrema of your children
      this.spaceBelowArray = [];
      this.spaceLeftArray = [];
      this.spaceRightArray = [];
      this.children.forEach(child => {
        // also respect the additional space due to the natural placement of the children
        this.spaceBelowArray.push(child.reservedSpaceBelow + child.gridOffsetToParent.y);
        this.spaceLeftArray.push(child.reservedSpaceLeft - child.gridOffsetToParent.x);
        this.spaceRightArray.push(child.reservedSpaceRight + child.gridOffsetToParent.x);
      });
      // get maximum values and set them as yours
      this.reservedSpaceBelow = Math.max.apply(Math, this.spaceBelowArray);
      this.reservedSpaceLeft = Math.max.apply(Math, this.spaceLeftArray);
      this.reservedSpaceRight = Math.max.apply(Math, this.spaceRightArray);
    }
  }

  getParentSpaceRequirements() {
    // how much space does your parent need in your direction without you?
    let parentSpaceBelow = 0;
    let parentSpaceLeft = 0;
    let parentSpaceRight = 0;
    
    // maybe it was your turn before your parents --> then wait until parent
    // arrays are properly set
    if (this.parent!.spaceBelowArray.length > 0) {
      // get the parent space arrays excluding yourself
      let excludingSpaceArray = (
        spaceArray: "spaceBelowArray" | "spaceLeftArray" | "spaceRightArray"
      ) => this
        .parent![spaceArray]
        .slice(this.indexForParent + 1)
        .concat(this.parent![spaceArray].slice(0, this.indexForParent));

      let excludingSpaceBelowArray = excludingSpaceArray("spaceBelowArray");
      let excludingSpaceLeftArray  = excludingSpaceArray("spaceLeftArray");
      let excludingSpaceRightArray = excludingSpaceArray("spaceRightArray");

      // get the maximum values again
      parentSpaceBelow = Math.max.apply(Math, excludingSpaceBelowArray);
      parentSpaceLeft = Math.max.apply(Math, excludingSpaceLeftArray);
      parentSpaceRight = Math.max.apply(Math, excludingSpaceRightArray);
      // add this to your reserved space, but be careful how
    }

    return [parentSpaceBelow, parentSpaceLeft, parentSpaceRight];
  }

  reserveSpace() {
    // find out how much distance you need to your parent so that you do
    // not overlap with its other children
    // this function must be iteratively called so that the changes can be
    // passed on from element to element
    let deltaVector = new Vector2D(0,0);

    if (this.hasParent) {
      let parentSpaceBelow = 0;
      let parentSpaceLeft = 0;
      let parentSpaceRight = 0;
      this.getOwnSpaceRequirements();      
      [parentSpaceBelow, parentSpaceLeft, parentSpaceRight] = this.getParentSpaceRequirements();
      
      // we may have actually moved in the right direction in another iteration
      // - so only move the difference by remembering reservedSpace[...]Old

      // now reserve this space by moving away in direction of your parent
      if (Math.sign(this.gridOffsetToParent.x) == 1) {
        // You are right of your parent --> parent is to your left --> need to
        // move to the right as much as we need space on the left
        if (this.reservedSpaceLeft + parentSpaceRight > this.reservedSpaceLeftOld) {
          deltaVector.x = this.reservedSpaceLeft + parentSpaceRight - this.reservedSpaceLeftOld;
          this.reservedSpaceLeftOld = this.reservedSpaceLeft + parentSpaceRight;
        } else {
          // reset to before
          this.reservedSpaceLeft = this.reservedSpaceLeftOld;
        }
        this.posChange(deltaVector);

      } else if (Math.sign(this.gridOffsetToParent.x) == -1) {
        // You are left of your parent --> parent is to your right --> need to
        // move to the left as much as we need space on the right
        if (this.reservedSpaceRight + parentSpaceLeft > this.reservedSpaceRightOld) {
          deltaVector.x = (this.reservedSpaceRight + parentSpaceLeft - this.reservedSpaceRightOld) * -1;
          this.reservedSpaceRightOld = this.reservedSpaceRight + parentSpaceLeft;
        } else {
          // reset to before
          this.reservedSpaceRight = this.reservedSpaceRightOld;
        }
        this.posChange(deltaVector);
      } else {
        //parent is above or below you
      }

      // if(this.id==2){ //for debugging purposes
      // 	if(Math.sign(this.gridOffsetToParent.x) == 1){
      // 		console.log("i am RIGHT of my parent who has id", this.parent.id);
      // 		console.log("without me, parent needs space right:", parentSpaceRight);
      // 		console.log("in direction of my parent I need space:", this.reservedSpaceLeft, "for my children");
      // 		console.log("combined i now hold distance to parent:", this.reservedSpaceLeft_old);
      // 	} else {
      // 		console.log("i am LEFT of my parent who has id", this.parent.id);
      // 		console.log("without me, parent needs space left:", parentSpaceLeft);
      // 		console.log("in direction of my parent I need space:", this.reservedSpaceRight, "for my children");
      // 		console.log("combined i now hold distance to parent:", this.reservedSpaceRight_old);
      // 	}
      // 	//console.log("i increased the distance to my parent by", deltaVector.x);
      // 	console.log(this);
      // }
    }

    // return deltaVector so that the algorithm on the outside can see if we changed anything
    return deltaVector;
  }

  addParent(parent: StructuredElement, deltaToParent: Vector2D, forceAcceptance: boolean) {
    // is automatically called when a parent adds a child --> see addChild(...)

    // decline if you already have a parent
    if (this.hasParent) {
      if((!forceAcceptance) && SETTINGS.SHOWDEBUGGINGINFO){
        // protest
        console.log("ID:",this.id,"says: <I already have a parent> to ID",parent.id);
      }
      return false;
    }

    this.hasParent = true;
    this.parent = parent;
    this.indexForParent = parent.children.length;
    parent.children.push(this);
    // overwrite existing references to possibly other parents
    this.gridOffsetToParent.x = 0;
    this.gridOffsetToParent.y = 0;
    this.posChange(deltaToParent);
    return true
  }

  addChild(child: StructuredElement, forceAcceptance:boolean = false, line_max_i_ka:number = 0, lineCimKey:string = "standard connection", lineID:number = -1, useOutputPort:boolean = false){
    let childDeltaToParent = new Vector2D(0,0);
    let acceptChild = true;

    if(!forceAcceptance){
      // if forceAcceptance == false this should be the first try of adding this child
      // need to draw a cable to your child
      // if you are a trafo, the child must be connected to your other port
      let childUseOutputPort = false;
      if(child.typeDescriptor == "trafo"){
        childUseOutputPort = true;
      }
      
      let newCable = new Cable(
        this.state,
        this,
        child,
        useOutputPort,
        childUseOutputPort,
        line_max_i_ka,
        lineCimKey,
      );
      this.state.cablesArray.push(newCable);
      // if this corresponds to a real line, need to add it to the line-dict
      if(lineID != -1){
        this.state.lineDict[lineCimKey] = newCable;
        this.state.lineDict[lineCimKey].id = lineID;
      }
      
    }

    // depending on how many children you have, evaluate the offset where to
    // place the child in referenz to this parent
    switch (this.children.length) {
      case 0:
        // place below
        childDeltaToParent.y = 1;
        break;

      case 1:
        // place left
        childDeltaToParent.x = -1;
        break;

      case 2:
        // place right
        childDeltaToParent.x = 1;
        break;

      default:
        // cannot deal with this!
        // Decline, maybe the child can be the parent of another node?
        acceptChild = false;
    }

    if (forceAcceptance) acceptChild = true;

    if (acceptChild) {
      // if your parent is in the direction you want to place the child, place it one further below
      if ((
          (Math.sign(this.gridOffsetToParent.x) == 1) &&
          (childDeltaToParent.x == 1)
        ) || (
          (Math.sign(this.gridOffsetToParent.y) == -1) &&
          (childDeltaToParent.x == -1)
        )) {
        childDeltaToParent.y += 1;
      }
      // bus to non-bus connections are special and need an extra y-offset of 0.5
      if (((this.typeDescriptor == "bus") && !(child.typeDescriptor == "bus"))
        || (!(this.typeDescriptor == "bus") && (child.typeDescriptor == "bus"))) {
        childDeltaToParent.y += 0.5;
      }

      child.addParent(this, childDeltaToParent, forceAcceptance);
    }

    return acceptChild;
  }

  override drawID() {
    // print the ORIGINAL type and id
    let typeDescription = this.typeDescriptor;
    // shorten long names
    if(typeDescription == "generator") typeDescription = "gen";

    drawText(
      this.state,
      typeDescription + " " + this.id,
      SETTINGS.IDTEXT,
      this.pos.x,
      this.pos.y - SETTINGS.IDTEXTDISTANCETOOBJECT - SETTINGS.SELECTBORDERSIZE
    );
  }
}
