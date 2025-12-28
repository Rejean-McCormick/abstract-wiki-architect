import pgf
from typing import Any, Union, Dict, List
from app.core.domain.frame import BioFrame

class NinaiToGFConverter:
    """
    Enterprise-Grade Converter: Domain Objects -> GF Abstract Syntax Trees.
    
    Acts as the 'Translation Layer' between Python Domain Models (BioFrame)
    and the Grammatical Framework's Type System.
    """

    def convert(self, node: Union[BioFrame, Dict[str, Any], str]) -> pgf.Expr:
        """
        Main Dispatcher. Routes input to the correct specific handler.
        """
        # 1. Domain Object Strategy (The "Green Path")
        # Handles strict Python objects produced by NinaiAdapter
        if isinstance(node, BioFrame):
            return self._convert_bio_frame(node)

        # 2. Raw Ninai Strategy (The "Red Path" / Prototype)
        # Handles recursive dictionary structures: {"function": "mkS", "args": [...]}
        if isinstance(node, dict):
            return self._convert_raw_node(node)

        # 3. Primitive Strategy (Literals)
        # Wraps raw strings into GF literals
        if isinstance(node, str):
            return pgf.readExpr(f'"{node}"')

        raise ValueError(f"NinaiToGF: Unsupported node type '{type(node)}'.")

    def _convert_bio_frame(self, frame: BioFrame) -> pgf.Expr:
        """
        Extracts data from the nested subject dictionary within the BioFrame.
        Enforces logic: Optional Nationality -> mkBioFull vs mkBioProf.
        """
        # --- DATA EXTRACTION ---
        # The NinaiAdapter puts data into the 'subject' dictionary
        data = frame.subject if isinstance(frame.subject, dict) else {}
        
        name = data.get("name", "Unknown")
        profession = data.get("profession", "person")
        nationality = data.get("nationality")

        # --- GF EXPRESSION CONSTRUCTION ---
        
        # A. Prepare the Subject (Entity)
        # Grammar expects: mkEntityStr : String -> Entity
        subject_expr = pgf.Expr("mkEntityStr", [pgf.readExpr(f'"{name}"')])

        # B. Prepare the Profession (CN)
        # Grammar expects: strProf : String -> Profession
        prof_expr = pgf.Expr("strProf", [pgf.readExpr(f'"{profession}"')])

        # C. Decision Logic based on Data Availability
        if nationality:
            # Case 1: Full Bio (Nationality exists)
            # Grammar expects: strNat : String -> Nationality
            nat_str_expr = pgf.Expr("strNat", [pgf.readExpr(f'"{nationality}"')])
            
            # Construct: mkBioFull Entity Profession Nationality
            return pgf.Expr("mkBioFull", [subject_expr, prof_expr, nat_str_expr])
        else:
            # Case 2: Partial Bio (No Nationality)
            # Construct: mkBioProf Entity Profession
            return pgf.Expr("mkBioProf", [subject_expr, prof_expr])

    def _convert_raw_node(self, node: Dict[str, Any]) -> pgf.Expr:
        """
        Handler for Raw Ninai Nodes (Recursive).
        """
        if "function" not in node:
             raise ValueError(f"NinaiToGF: Raw node missing 'function' key: {node}")
        
        fn_name = node["function"]
        # Recursively convert all arguments
        args = [self.convert(arg) for arg in node.get("args", [])]
        
        return pgf.Expr(fn_name, args)