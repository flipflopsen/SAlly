import State from "../state";

export default function drawRectangle(
  state: State,
  atPosX: number,
  atPosY: number,
  mySizeX: number,
  mySizeY: number,
  color: string
) {
  // the native draw-functions don't use Vector2D's as parameters,
  // so this function sticks with their theme
  state.bufferContext.rect(atPosX, atPosY, mySizeX, mySizeY);
  state.bufferContext.fillStyle = color;
  state.bufferContext.fill();	// so that we don't just have an infinitely thin line
}
