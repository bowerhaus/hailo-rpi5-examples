import math

class Point2D:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point2D({self.x}, {self.y})"

    def round(self, n=2):
        return Point2D(round(self.x, n), round(self.y, n))

    def subtract(self, p):
        return Point2D(self.x - p.x, self.y - p.y)

    def magnitude(self):
        return (self.x**2 + self.y**2)**0.5

    def direction(self):
        angle = math.degrees(math.atan2(self.y, self.x))
        return angle if angle >= 0 else angle + 360