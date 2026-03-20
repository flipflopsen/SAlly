export default class TextBlueprint {
  constructor(
    public fontType: string,
    public fontSize: number,
    public fillStyle: string
  ) {}

  get font(): string {
    return `${this.fontSize}pt ${this.fontType}`;
  }
}
