export default function fastDrawImage(
  myCanvas: CanvasRenderingContext2D,
  img: HTMLImageElement,
  posX: number,
  posY: number,
  sizeX: number,
  sizeY: number
) {
  // browser can render images faster when the coordinates are whole integers
  myCanvas.drawImage(
    img,
    Math.floor(posX),
    Math.floor(posY),
    Math.floor(sizeX),
    Math.floor(sizeY)
  );
}
