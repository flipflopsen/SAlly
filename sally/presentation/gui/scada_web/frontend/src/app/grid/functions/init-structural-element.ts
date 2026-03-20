import StructuredElement from "../classes/structured-element";
import Bus from "../classes/bus";
import ExtGrid from "../classes/ext-grid";
import Trafo from "../classes/trafo";
import Load from "../classes/load";
import Vector2D from "../classes/vector-2d";
import State from "../state";
import Generator from "../classes/generator";
import Switch from "../classes/switch";

export default function initStructuralElement(
  state: State,
  ElementType: typeof ExtGrid | typeof Generator | typeof Load | typeof Trafo| typeof Switch,
  cim_id: string,
  elementInfo: Record<string, any>,
  defaultGridPos = new Vector2D(0, 0)
) {
  let elementName = elementInfo["name"];
  // bus names are a bit weird, e.g. "Lehe MV - 2/c_load_3_2" --> we only want the first part
  if (ElementType == Bus) elementName = elementName.split("/")[0];

  let newElement = new ElementType(
    state,
    elementName,
    elementInfo,
    cim_id,
  );

  // the other elements reference the busses and will connect to them
  // so there is nothing left to do for busses here
  if (ElementType == Bus) return newElement;

  let myParent: StructuredElement | null = null;
  let myChild: StructuredElement | null = null;
  let acceptedChild = false;

  // for ExtGrid "relations" shows where the child bus is, because ExtGrid is always a parent itself
  if (ElementType == ExtGrid){
    myChild = state.busDict[elementInfo["relations"][0]];
    newElement.stepsAwayFromRootNode = 0;
  } else if (ElementType == Trafo) {
    myParent = state.busDict[elementInfo["hv"]["bus"]];
    myChild = state.busDict[elementInfo["lv"]["bus"]];
  } else if (ElementType == Switch) {
    // you are outside the parent-child relationships!
    let firstChild = state.busDict[elementInfo["relations"][0]];
    let secondChild = state.busDict[elementInfo["relations"][1]];
    newElement.addChild(firstChild, false, 0, "standard connection", -1, false);
    firstChild.stepsAwayFromRootNode = 1;
    newElement.addChild(secondChild, false, 0, "standard connection", -1, true);
    secondChild.stepsAwayFromRootNode = 1;

  } else if (ElementType != Bus){
    // if you only have one relation and are not an ext_grid or trafo element, that relation defines your parent
    if (elementInfo["relations"].length == 1){
      myParent = state.busDict[elementInfo["relations"][0]];
    }
  }

  // if you have a parent, introduce yourself
  if (myParent instanceof StructuredElement) {
    myParent.addChild(newElement);
  } else {
    // if you have no parent, position yourself on the grid
    newElement.posChange(defaultGridPos);
  }

  // if you have a child add it if you can (which is the case if your are ext_grid or trafo)
  if (myChild instanceof StructuredElement) {
    acceptedChild = newElement.addChild(myChild);
    if(!(acceptedChild)){
      // if the child finds no other parent, we will force-add it later
      state.tryToAddChildLaterList.push([newElement, myChild])
    }    
    myChild.stepsAwayFromRootNode = 1;
  }

  return newElement;
}
