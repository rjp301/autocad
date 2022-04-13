from dataclasses import dataclass
from typing import List
import math

from helpers.geometry import avg_lines,join_lines
from helpers.quadtree import QuadTree,find_boundary


@dataclass
class Polyline:
  vertices: List[Point]

  def __post_init__(self):
    assert len(self.vertices) > 1, "Need vertices to make a Polyline"
    self.vertices = list(dict.fromkeys(self.vertices))
    self.segments = [Line(self.vertices[i-1],v) for i,v in enumerate(self.vertices) if i > 0]
    
    self.qtree = QuadTree(find_boundary(self.vertices))
    self.q_radius = max(i.length() for i in self.segments)
    for i in self.vertices: self.qtree.insert(i)
    
    if self.KPs:
      # self.KPs = sorted(self.KPs,key=lambda i: i.label)
      self.qtree_KP = QuadTree(find_boundary(self.KPs))
      for i in self.KPs: self.qtree_KP.insert(i)

  def __repr__(self):
    points = [f"{i.x} {i.y}" for i in self.vertices]
    return f"LINESTRING({', '.join(points)})"

  def nearest_vertex(self,node,radius=None):
    radius = self.q_radius if not radius else radius
    points = []
    self.qtree.query_radius(node,radius,points)
    if not points:
      raise ValueError(f"No vertices within a {radius:.2f} radius of {node}")
    return node.nearest(points)

  def remove_vertex(self,index):
    new_vertices = self.vertices.copy()
    del new_vertices[index]
    return Polyline(new_vertices,self.KPs)

  def insert_vertex(self,index,node):
    new_vertices = self.vertices.copy()
    new_vertices.insert(index,node)
    return Polyline(new_vertices,self.KPs)

  def length(self):
    return sum(seg.length() for seg in self.segments)

  def move_to_ln(self,node,radius=None):
    """Returns the coordinates of node if it were moved to be coincident with the line along the shortest possible path"""
    # Determine nearest vertex to the node
    nearest_pt = self.nearest_vertex(node,radius=radius)
    nearest_pt_dist = nearest_pt.pt_to_pt(node)

    # Sort segments by distance to node
    for segment,distance in sorted(zip(self.segments,[i.dist_to_pt(node) for i in self.segments]), key=lambda i: i[1]):
      # If a vertex is the nearest part of the polyline to the node, return vertex
      if distance >= nearest_pt_dist: return nearest_pt
      
      # Move pt to line segment and see if on line
      moved_pt = segment.move_to_ln(node)
      if segment.on_line(moved_pt):
        return moved_pt

    return nearest_pt

  def reverse(self):
    new_vertices = self.vertices
    new_vertices.reverse()
    return Polyline(new_vertices)

  def which_segment(self,node,radius=None):
    """Returns the line segment in the polyline which is both closest to the given point and which the point can be moved perpindicularly to be coincident with"""
    new_pt = self.move_to_ln(node,radius=radius)
    return next((i for i in self.segments if i.on_line(new_pt)),False)

  def along(self,dt):
    """Returns a point at a certain distance along the polyline"""
    assert dt <= self.length(), "Distance must be less than polyline length"
    assert dt >= 0, "Distance must be positive"
    length = 0
    for segment in self.segments:
      length += segment.length()
      if length >= dt:
        return segment.along(dt - (length - segment.length()))
  
  def on_line(self,node):
    """Determine if node is coincident with Polyline"""
    segment = self.which_segment(node)
    if segment: return segment.on_line(node)
    return False

  def dist_to_ln(self,node,signed=False):
    segment = self.which_segment(node)
    distance = segment.dist_to_pt(node)
    if signed: distance = distance * segment.which_side(node)
    return distance

  def which_side(self,node):
    segment = self.which_segment(node)
    return segment.which_side(node)

  def pt_along(self,node,radius=None):
    """Returns distance from the start of the Polyline to a point when moving along it"""
    segment = self.which_segment(node,radius=radius)
    index = self.segments.index(segment)
    length = sum([seg.length() for seg in self.segments[:index]])
    length += segment.pt_along(node)
    return length

  def pt_to_pt_along(self,p1,p2):
    """Returns the distance between two points when moving along the Polyline"""
    d1 = self.pt_along(p1)
    d2 = self.pt_along(p2)
    return abs(d1 - d2)

  def splice(self,p1,p2,radius=None):
    assert isinstance(p1,Point), "p1 not a point"
    assert isinstance(p2,Point), "p2 not a point"

    p1.segment = self.which_segment(p1,radius=radius)
    p2.segment = self.which_segment(p2,radius=radius)

    p1.moved = p1.segment.move_to_ln(p1)
    p2.moved = p2.segment.move_to_ln(p2)

    # if p1.moved == p2.moved: return None

    p1.index = self.segments.index(p1.segment)
    p2.index = self.segments.index(p2.segment)

    if p1.index <= p2.index: pt_beg,pt_end = p1,p2
    else: pt_end,pt_beg = p1,p2

    vertices = []
    vertices.append(pt_beg.moved)
    index = pt_beg.index

    while index < pt_end.index:
      vertices.append(self.segments[index].p2)
      index += 1

    vertices.append(pt_end.moved)
    return Polyline(vertices)

  def perp_angle(self,node):
    if node in self.vertices:
      index = self.vertices.index(node)
      if node == self.vertices[0]: return self.segments[0].angle() + 90
      if node == self.vertices[-1]: return self.segments[0].angle() + 90
      s1 = self.segments[index-1]
      s2 = self.segments[index]
      angle3 = avg_lines([s1,s2]).angle() + 90
      return angle3
    return self.which_segment(node).angle() + 90    

  def intersects_pl(self,other):
    inter = []
    for segment in self.segments:
      intersections = [segment.intersects(i) for i in other.segments]
      intersections = [i for i in intersections if i]
      intersections.sort(key=lambda i: segment.pt_along(i))
      inter += intersections
    return inter
  
  def offset_simple(self,dist):
    if dist == 0: return self
    offset_lines = [i.offset(dist) for i in self.segments]
    return join_lines(offset_lines)

  def offset(self,dist):
    if dist == 0: return self
    offset = self.offset_simple(dist)

    inter = [offset.vertices[0]]
    inter += offset.intersects_pl(offset)
    inter += [offset.vertices[-1]]

    inter_self = [i for i in inter if i not in offset.vertices]
    overlaps = []
    for i in inter_self:
      i1 = inter.index(i)
      i2 = inter.index(i,i1+1)
      overlap = (i1,i2)
      if overlap not in overlaps: overlaps.append(overlap)

    overlaps = [i for i in overlaps if not any((i[0] > j[0] and i[1] < j[1]) for j in overlaps)]
    inter = [i for index,i in enumerate(inter) if not any((index >= j[0] and index < j[1]) for j in overlaps)]
    return Polyline(inter)

  def splice_KP(self,KP_beg,KP_end):
    pt_beg = self.from_KP(KP_beg,True)
    pt_end = self.from_KP(KP_end,True)
    new_KPs = [i for i in self.KPs if (i.label <= KP_end and i.label >= KP_beg)]
    new_vertices = self.splice(pt_beg,pt_end).vertices
    return Polyline(new_vertices,new_KPs)

  def elevation_at_pt(self,node):
    segment = self.which_segment(node)
    new_node = segment.move_to_ln(node)
    if not segment.on_line(new_node): return None
    
    tot_length = segment.length()
    pt_length = segment.pt_along(node)
    tot_vert = segment.p2.z - segment.p1.z
    pt_vert = pt_length * tot_vert / tot_length
    
    return pt_vert + segment.p1.z

  def ACAD(self,inc_elevation=False):
    """Outputs command list to draw the Polyline in AutoCAD"""
    command = []
    command.append("_.pline")
    for index,vertex in enumerate(self.vertices):
      if index == 0 and inc_elevation:
        command.append(f"_non {vertex.x},{vertex.y},{vertex.z}")
        continue
      command.append(f"_non {vertex.x},{vertex.y}")
    command.append("(SCRIPT-CANCEL)")
    return command

@dataclass
class Polygon:
  vertices: List[Point]

  def __post_init__(self):
    assert type(self.vertices) == list, "Vertices must a list of points"
    assert len(self.vertices) >= 3, "Polygon Error: Needs more points"
    
    if self.vertices[0] == self.vertices[-1]: self.vertices = self.vertices[:-1]
    self.segments = [Line(self.vertices[i-1],v) for i,v in enumerate(self.vertices)]
    self.qtree = QuadTree(find_boundary(self.vertices))
    for i in self.vertices: self.qtree.insert(i)

  def __repr__(self):
    points = [f"{i.x} {i.y} {i.z}" for i in self.vertices]
    return f"POLYGON(({', '.join(points)}))"

  def area(self) -> float:
    area = 0
    j = len(self.vertices) - 1
    for i in range(len(self.vertices)):
      p1 = self.vertices[j]
      p2 = self.vertices[i]
      area += (p1.x + p2.x) * (p1.y - p2.y)
      j = i
    return abs(area)/2

  # def vis_center(self):
  #   x,y = polylabel([[[pt.x,pt.y] for pt in self.vertices]])
  #   self.vis_pt = Point(x,y,label=self.label)
  #   return self.vis_pt

  def within(self,node) -> bool:
    outside = Point(min(i.x for i in self.vertices),min(i.y for i in self.vertices)).copy(-10,-10)
    line = Line(outside,node)
    intersections = line.intersects_pl(self)
    return len(intersections) % 2 == 1 # odd -> inside, even -> outside
  
  def envelope(self):
    pt_min = Point(min(i.x for i in self.vertices),min(i.y for i in self.vertices))
    pt_max = Point(max(i.x for i in self.vertices),max(i.y for i in self.vertices))
    return pt_min.pt_to_pt(pt_max)

  def centroid(self):
    x = sum(i.x for i in self.vertices)/len(self.vertices)
    y = sum(i.y for i in self.vertices)/len(self.vertices)
    return Point(x,y)

  def intersects_pl(self,other):
    intersections = [i.intersects(j) for i in self.segments for j in other.segments]
    return [i for i in intersections if i]

  def KML_coords(self):
    vertices = self.vertices + [self.vertices[0]]
    return [(i.x,i.y) for i in vertices]

  def ACAD_solid(self):
    assert len(self.vertices) == 3 or len(self.vertices) == 4, "Wrong number of vertices"
    command = "SOLID "
    command += f"{self.vertices[0].comm()} "
    command += f"{self.vertices[1].comm()} "
    command += f"{self.vertices[-1].comm()}"
    if len(self.vertices) > 3:
      command += f" {self.vertices[2].comm()}"
      command += "\n"
    else:
      command += "\n\n"
    return [command]

  def ACAD_mpoly(self):
    command = "MPOLYGON"
    for pt in self.vertices:
      command += f" {pt.comm()}"
    command += "\n"
    command += "C\nX"
    return [command]

  def ACAD(self):
    """Outputs command list to draw the Polyline in AutoCAD"""
    vertices = self.vertices + [self.vertices[0]]
    command = []
    command.append("_.pline")
    command += [f"_non {i.x},{i.y}" for i in vertices]
    command.append("(SCRIPT-CANCEL)")
    return command

  def offset(self,dist):
    lines = [i.offset(dist) for i in self.segments]
    joined = Polygon(join_lines(lines).vertices)
    return joined

  def plot(self,axis,style="k",**kwargs):
    x = [i.x for i in self.vertices] + [self.vertices[0].x]
    y = [i.y for i in self.vertices] + [self.vertices[0].y]
    axis.plot(x,y,style,**kwargs)

@dataclass
class Circle:
  origin: Point
  radius: float

  def within(self,node):
    return self.origin.pt_to_pt(node) < self.radius

  def to_poly(self,res=10):
    # res = approximate distance between points
    circumference = math.pi * 2 * self.radius
    num_points = int(circumference/res)
    angle = 360/num_points
    pts = [self.origin.copy_polar(self.radius,angle*i) for i in range(num_points)]
    return Polygon(pts)
 
  def intersects(self,line,segment=True):
    m,d = line.equation_mb()
    a,b,r = self.origin.x,self.origin.y,self.radius

    delta = r**2*(1 + m**2) - (b - m*a - d)**2

    if delta < 0: return []

    x1 = (a + b*m - d*m + math.sqrt(delta)) / (1 + m**2)
    x2 = (a + b*m - d*m - math.sqrt(delta)) / (1 + m**2)
    y1 = (d + a*m + b*m**2 + m*math.sqrt(delta)) / (1 + m**2)
    y2 = (d + a*m + b*m**2 - m*math.sqrt(delta)) / (1 + m**2)

    points = [Point(x1,y1),Point(x2,y1),Point(x1,y2),Point(x2,y2)]
    points = [i for i in points if i.pt_to_pt(self.origin) <= r*1.01 and i.pt_to_pt(self.origin) >= r*0.99]
    points = [i for i in points if line.on_line(i)] if segment else points
    return points

  def intersects_pl(self,other):
    assert isinstance(other,Polyline), "Other must be a polyline"
    intersections = []
    for seg in other.segments:
      intersections += self.intersects(seg,segment=True)
    return intersections

  def ACAD(self):
    command = []
    command += [f"_.circle _non {self.origin.comm()} {self.radius}"]
    return command

