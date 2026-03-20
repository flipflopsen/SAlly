export default class Vector2D {
  constructor(public x: number, public y: number) {}

  plus(other: Vector2D) {
    return new Vector2D(this.x + other.x, this.y + other.y);
  }

  minus(other: Vector2D) {
    return new Vector2D(this.x - other.x, this.y - other.y);
  }

  get length() {
    return Math.sqrt(this.x * this.x + this.y * this.y);
  }

  mult(scalar: number) {
    return new Vector2D(this.x * scalar, this.y * scalar);
  }

  equals(other: Vector2D) {
    return this.x == other.x && this.y == other.y;
  }

  copy() {
    return new Vector2D(this.x, this.y);
  }

  normed() {
    let length = this.length;
    return new Vector2D(this.x / length, this.y / length);
  }

  rotate(angle: number) {
    // see: https://matthew-brett.github.io/teaching/rotation_2d.html
    let beta = angle * Math.PI / 180;
    return new Vector2D(
      Math.cos(beta) * this.x - Math.sin(beta) * this.y,
      Math.sin(beta) * this.x + Math.cos(beta) * this.y
    );
  }
}
