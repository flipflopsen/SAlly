export default function download(
  filename: string,
  toSave: string
) {
  // this function is still useful for debugging purposes to extract what was saved

  // create a function that will generate anchor tag like this, then attach it to the page, and emulate a click.
  let element = document.createElement("a");
  element.setAttribute("href", "data:text/plain;charset=utf-8," + encodeURIComponent(toSave));
  element.setAttribute("download", filename);
  element.style.display = "none";
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
}
