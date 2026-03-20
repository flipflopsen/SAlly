import Vector2D from "../classes/vector-2d";
import State from "../state";
import ElectricElement from "../classes/electric-element";

export default function checkHitBoxes(state: State, atCoor: Vector2D) {
  let hitElementsArray: ElectricElement[] = [];

  // check in layer-order: cables first
  state.cablesArray.forEach(cable => {
    if (cable.isCoorInHitbox(atCoor)) {
      hitElementsArray.push(cable);
    }
  });
  state.electricComponentsArray.forEach(drawable => {
    if (drawable.isCoorInHitbox(atCoor)) {
      hitElementsArray.push(drawable);
    }
  });

  return hitElementsArray;
}
