import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.math.BigInteger;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.SecureRandom;
import java.security.cert.X509Certificate;
import java.util.Calendar;
import java.util.Date;
import java.util.List;
import java.util.Map;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationText;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.SignatureOptions;
import org.apache.pdfbox.util.Matrix;
import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.cert.jcajce.JcaCertStore;
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter;
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder;
import org.bouncycastle.cms.CMSProcessableByteArray;
import org.bouncycastle.cms.CMSSignedDataGenerator;
import org.bouncycastle.cms.jcajce.JcaSignerInfoGeneratorBuilder;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.operator.jcajce.JcaDigestCalculatorProviderBuilder;

import com.google.zxing.BarcodeFormat;
import com.google.zxing.EncodeHintType;
import com.google.zxing.common.BitMatrix;
import com.google.zxing.qrcode.QRCodeWriter;

/**
 * Builds the tools/ cases that need real cryptography or a QR code: PDFBox 3.0.8, BouncyCastle
 * 1.85 and ZXing core 3.5 on the classpath. Usage: ToolCases REPORT_PDF OUT_DIR. The signing key
 * is generated on every run and thrown away, so signatures differ between runs.
 */
public class ToolCases {
    static KeyPair keys;
    static X509Certificate cert;

    public static void main(String[] args) throws Exception {
        File report = new File(args[0]);
        File out = new File(args[1]);
        out.mkdirs();
        makeIdentity();
        byte[] signed = sign(java.nio.file.Files.readAllBytes(report.toPath()), "Approved by facilities");
        write(new File(out, "signature-self-signed-valid.pdf"), signed);
        write(new File(out, "signature-then-incremental-edit.pdf"), editAfterSigning(signed));
        write(new File(out, "signature-two-signatures.pdf"), sign(signed, "Counter-signed by finance"));
        qrSeparated(report, new File(out, "qr-separator-pages-auto-split.pdf"));
    }

    static void makeIdentity() throws Exception {
        KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
        gen.initialize(2048, new SecureRandom());
        keys = gen.generateKeyPair();
        X500Name name = new X500Name("CN=Corpus Test Signer, O=Example, C=GB");
        Date from = new Date(1767225600000L);
        Date to = new Date(2082758400000L);
        JcaX509v3CertificateBuilder b = new JcaX509v3CertificateBuilder(name, BigInteger.valueOf(42), from, to, name, keys.getPublic());
        cert = new JcaX509CertificateConverter().getCertificate(
                b.build(new JcaContentSignerBuilder("SHA256withRSA").build(keys.getPrivate())));
    }

    static byte[] cms(InputStream content) throws java.io.IOException {
        try {
            return cmsChecked(content);
        } catch (java.io.IOException e) {
            throw e;
        } catch (Exception e) {
            throw new java.io.IOException(e);
        }
    }

    static byte[] cmsChecked(InputStream content) throws Exception {
        CMSSignedDataGenerator g = new CMSSignedDataGenerator();
        ContentSigner s = new JcaContentSignerBuilder("SHA256withRSA").build(keys.getPrivate());
        g.addSignerInfoGenerator(new JcaSignerInfoGeneratorBuilder(new JcaDigestCalculatorProviderBuilder().build()).build(s, cert));
        g.addCertificates(new JcaCertStore(List.of(cert)));
        return g.generate(new CMSProcessableByteArray(content.readAllBytes()), false).getEncoded();
    }

    static byte[] sign(byte[] pdf, String reason) throws Exception {
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            PDSignature sig = new PDSignature();
            sig.setFilter(PDSignature.FILTER_ADOBE_PPKLITE);
            sig.setSubFilter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED);
            sig.setName("Corpus Test Signer");
            sig.setReason(reason);
            Calendar when = Calendar.getInstance();
            when.setTimeInMillis(1794787200000L);
            sig.setSignDate(when);
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            SignatureOptions opts = new SignatureOptions();
            opts.setPreferredSignatureSize(12000);
            doc.addSignature(sig, ToolCases::cms, opts);
            doc.saveIncremental(bos);
            return bos.toByteArray();
        }
    }

    static byte[] editAfterSigning(byte[] signed) throws Exception {
        try (PDDocument doc = Loader.loadPDF(signed)) {
            PDPage page = doc.getPage(0);
            PDAnnotationText note = new PDAnnotationText();
            note.setRectangle(new PDRectangle(520, 760, 20, 20));
            note.setContents("Figures changed after approval");
            page.getAnnotations().add(note);
            page.getCOSObject().setNeedToBeUpdated(true);
            doc.getDocumentInformation().setTitle("Quarterly Facilities Report (revised)");
            doc.getDocumentInformation().getCOSObject().setNeedToBeUpdated(true);
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            doc.saveIncremental(bos);
            return bos.toByteArray();
        }
    }

    static void drawQr(PDPageContentStream cs, String text, float x, float y, float size, float angle) throws Exception {
        BitMatrix m = new QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, 0, 0, Map.of(EncodeHintType.MARGIN, 0));
        float cell = size / m.getWidth();
        cs.saveGraphicsState();
        cs.transform(Matrix.getRotateInstance(Math.toRadians(angle), x, y));
        for (int r = 0; r < m.getHeight(); r++)
            for (int c = 0; c < m.getWidth(); c++)
                if (m.get(c, r)) cs.addRect(c * cell, size - (r + 1) * cell, cell, cell);
        cs.fill();
        cs.restoreGraphicsState();
    }

    static void qrSeparated(File report, File target) throws Exception {
        try (PDDocument doc = new PDDocument(); PDDocument src = Loader.loadPDF(report)) {
            String[] labels = {"Document A", "Document B", "Document C"};
            for (int i = 0; i < 3; i++) {
                PDPage p = doc.importPage(src.getPage(0));
                try (PDPageContentStream cs = new PDPageContentStream(doc, p, PDPageContentStream.AppendMode.APPEND, true)) {
                    cs.beginText();
                    cs.setFont(new PDType1Font(Standard14Fonts.FontName.HELVETICA_BOLD), 14);
                    cs.newLineAtOffset(400, 40);
                    cs.showText(labels[i]);
                    cs.endText();
                }
                if (i == 2) break;
                PDPage sep = new PDPage(PDRectangle.A4);
                doc.addPage(sep);
                try (PDPageContentStream cs = new PDPageContentStream(doc, sep)) {
                    if (i == 0) {
                        drawQr(cs, "https://stirlingpdf.com", 197, 320, 200, 0);
                    } else {
                        drawQr(cs, "https://github.com/Stirling-Tools/Stirling-PDF", 380, 560, 90, 12);
                        cs.beginText();
                        cs.setFont(new PDType1Font(Standard14Fonts.FontName.HELVETICA), 11);
                        cs.newLineAtOffset(72, 700);
                        cs.showText("Separator sheet: small QR code, turned 12 degrees, with text beside it.");
                        cs.endText();
                    }
                }
            }
            doc.save(target);
        }
    }

    static void write(File f, byte[] b) throws Exception {
        try (FileOutputStream o = new FileOutputStream(f)) {
            o.write(b);
        }
    }
}
