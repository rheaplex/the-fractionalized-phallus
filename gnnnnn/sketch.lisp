(ql:quickload '(:cl-gltf :alexandria))

(defpackage :gltf-modifier
  (:use :cl :alexandria)
  (:local-nicknames (:gltf :org.shirakumo.fraf.gltf)))

(in-package :gltf-modifier)

(defun add-shapes-mesh (gltf shapes)
  (flet ((gltf:make-primitive (shape)
           (gltf:make-mesh-primitive
            gltf
            (convex-mesh-vertices shape)
            (convex-mesh-faces shape)
            '(:position)
            :matrix (marr4 (primitive-local-transform shape)))))
    (gltf:make-indexed 'gltf:mesh gltf
                       :primitives (map 'vector #'gltf:make-primitive shapes))))

(let* ((root (make-instance 'gltf:gltf))
      (scene (make-instance 'gltf:scene))
      (mesh (make-instance 'gltf:mesh))
      (primitive (gltf:make-mesh-primitive))
      (node (make-instance 'gltf:node))
      (buffer (make-instance 'gltf:static-buffer :gltf root :uri "data:application/octet-stream;base64,AAABAAIAAAAAAAAAAAAAAAAAAAAAAIA/AAAAAAAAAAAAAAAAAACAPwAAAAA="))
      (view1 (make-instance 'gltf:buffer-view :idx 0 :start 0 :byte-offset 0 :byte-length 6 :target 'element-array-buffer))
      (view2 (make-instance 'gltf:buffer-view :idx 0 :start 8 :target 'array-buffer))
      ;;(accessor1 (make-instance 'gltf:accessor))
      ;;(accessor2 (make-instance 'gltf:accessor))
      )
  ;;(setf (gltf:buffer view1) 0)
  t)

(defun load-gltf (path)
  "Load a GLTF file from the given path"
  (gltf:parse path))

(defun get-mesh-primitive (gltf mesh-index primitive-index)
  "Get a specific primitive from a mesh"
  (let* ((mesh (elt (gltf:meshes gltf) mesh-index))
         (primitive (elt (gltf:primitives mesh) primitive-index)))
    primitive))

(defun modify-triangle-mesh (g mesh-index primitive-index modifier-fn)
  "Modify vertices of a triangle mesh using modifier-fn"
  (let* ((primitive (get-mesh-primitive g mesh-index primitive-index))
         ;;(position-accessor (gethash :position (gltf:attributes primitive)))
         ;;(vertices (position-accessor g))
         )
    (format t "~a~%" primitive)
    ;; Modify vertices in-place using the provided function
    ;;(loop for i from 0 below (length vertices) by 3
    ;;      for vertex = (subseq vertices i (+ i 3))
    ;;      do (let ((modified (funcall modifier-fn vertex)))
    ;;           (replace vertices modified :start1 i :end1 (+ i 3))))
    )
  )

(defun scale-vertex (vertex scale)
  "Scale a vertex by a given factor"
  (map 'vector (lambda (x) (* x scale)) vertex))

;; Example usage
(defun main ()
  (gltf:with-gltf (g #p"src/1k.glb")
  (let* (;; Scale all vertices by 2.0
         (modified-g (modify-triangle-mesh g 0 0
                         (lambda (vertex) (scale-vertex vertex 2.0)))))
    ;; Save the modified GLTF
    (gltf:serialize modified-g #p"./output.gltf"))))

;; Run the example
(main)
